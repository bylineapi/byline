# scheduler.py - Programador de tareas con APScheduler para scraping y limpieza

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session_maker
from models import Source, Article, ArticleStatusEnum, SourceProfile, ActivityLog
from scraper import fetch_rss, MIN_CONFIDENCE_FOR_PROFILER
from scorer import ImpactScorer

logger = logging.getLogger(__name__)

# Intervalos en minutos
SCRAPING_INTERVAL_MINUTOS = 15
CLEANUP_INTERVAL_HORAS = 24

scheduler = AsyncIOScheduler()
scorer = ImpactScorer()


# ─── Job 1: Scraping ─────────────────────────────────────────────────────────

async def scraping_job(force_date: Optional[datetime] = None, source_ids: Optional[list[int]] = None):
    """
    Itera todas las fuentes activas, obtiene artículos nuevos via RSS,
    los puntúa y guarda en BD los que no sean 'discarded'.
    
    IMPORTANTE: Usa sesiones de BD de corta duración para evitar timeouts.
    
    Args:
        force_date: Si se proporciona, usa esta fecha para todos los artículos (solo para pruebas)
        source_ids: Lista opcional de IDs de fuentes a procesar. Si es None, procesa todas las fuentes activas.
    """
    logger.info("Iniciando scraping_job...")
    
    # Sesión 1: Obtener fuentes activas
    async with get_session_maker() as db:
        query = select(Source).where(Source.is_active.is_(True))
        
        # Si se especifican source_ids, filtrar solo esas fuentes
        if source_ids:
            query = query.where(Source.id.in_(source_ids))
            logger.info("Scraping dirigido a %d fuentes específicas: %s", len(source_ids), source_ids)
        
        result = await db.execute(query)
        fuentes = result.scalars().all()
        
        if not fuentes:
            if source_ids:
                logger.info("No se encontraron fuentes activas con los IDs proporcionados: %s", source_ids)
            else:
                logger.info("No hay fuentes activas para scrapear.")
            return
        
        # Obtener artículos recientes para scoring
        hace_2h = datetime.utcnow() - timedelta(hours=2)
        result_recent = await db.execute(
            select(Article).where(Article.created_at >= hace_2h)
        )
        articulos_recientes = result_recent.scalars().all()
    # La sesión se cierra aquí
    
    # Convertir a dicts para el scorer
    articulos_recientes_dicts = [
        {
            "source_id": a.source_id,
            "title": a.title,
            "content": a.content,
            "published_at": a.published_at or a.created_at,
        }
        for a in articulos_recientes
    ]
    
    total_nuevos = 0
    
    # Procesar cada fuente con su propia sesión
    for fuente in fuentes:
        try:
            # Sesión 2: Obtener perfil de la fuente
            async with get_session_maker() as db:
                result_profile = await db.execute(
                    select(SourceProfile).where(SourceProfile.source_id == fuente.id)
                )
                profile = result_profile.scalar_one_or_none()
                profile_dict = None
                
                if profile and profile.confidence_score >= MIN_CONFIDENCE_FOR_PROFILER:
                    profile_dict = {
                        "title_selector": profile.title_selector,
                        "body_selector": profile.body_selector,
                        "image_selector": profile.image_selector,
                        "date_selector": profile.date_selector,
                        "author_selector": profile.author_selector,
                        "confidence_score": profile.confidence_score,
                    }
            # La sesión se cierra aquí
            
            # Scraping de la fuente (puede tardar varios minutos)
            articulos_crudos, nuevo_perfil = await fetch_rss(fuente, profile_dict, force_date)
            
            # Guardar el nuevo perfil si se aprendió automáticamente
            if nuevo_perfil:
                async with get_session_maker() as db_prof:
                    try:
                        # Buscar perfil existente
                        stmt = select(SourceProfile).where(SourceProfile.source_id == fuente.id)
                        res = await db_prof.execute(stmt)
                        profile_obj = res.scalar_one_or_none()
                        
                        if profile_obj:
                            # Actualizar perfil existente
                            profile_obj.title_selector = nuevo_perfil['title_selector']
                            profile_obj.body_selector = nuevo_perfil['body_selector']
                            profile_obj.image_selector = nuevo_perfil['image_selector']
                            profile_obj.date_selector = nuevo_perfil['date_selector']
                            profile_obj.author_selector = nuevo_perfil['author_selector']
                            profile_obj.confidence_score = nuevo_perfil['confidence_score']
                            profile_obj.last_verified = datetime.utcnow()
                        else:
                            # Crear nuevo perfil
                            new_profile = SourceProfile(
                                source_id=fuente.id,
                                title_selector=nuevo_perfil['title_selector'],
                                body_selector=nuevo_perfil['body_selector'],
                                image_selector=nuevo_perfil['image_selector'],
                                date_selector=nuevo_perfil['date_selector'],
                                author_selector=nuevo_perfil['author_selector'],
                                confidence_score=nuevo_perfil['confidence_score'],
                                last_verified=datetime.utcnow()
                            )
                            db_prof.add(new_profile)
                        
                        await db_prof.commit()
                        logger.info("🤖 Perfil guardado automáticamente para fuente %s", fuente.name)
                    except Exception as prof_err:
                        logger.error("Error guardando perfil automático: %s", prof_err)
            
            if not articulos_crudos:
                logger.info("Fuente %s: No se extrajeron artículos", fuente.name)
                continue
            
            # Sesión 3: Guardar artículos encontrados
            # IMPORTANTE: Abrir sesión DESPUÉS del scraping para evitar timeout
            # PROCESAR ARTÍCULOS DE UNO EN UNO con sesiones independientes
            for idx, data in enumerate(articulos_crudos):
                try:
                    # Cada artículo usa su propia sesión de BD
                    async with get_session_maker() as db:
                        logger.debug(
                            "Procesando artículo: %s (source_id: %d)",
                            data.get("title", "Sin título")[:80],
                            data["source_id"]
                        )
                        
                        # Verificar si ya existe por original_url
                        existe = await db.execute(
                            select(Article).where(
                                Article.original_url == data["original_url"]
                            )
                        )
                        if existe.scalar_one_or_none():
                            logger.info("️ Artículo duplicado, saltando: %s", data.get("title", "")[:60])
                            continue
                        
                        # GUARDAR TODOS los artículos - sin filtrar por score
                        article = Article(
                            source_id=data["source_id"],
                            title=data["title"],
                            content=data["content"],
                            excerpt=data.get("excerpt", ""),
                            image_url=data.get("image_url"),
                            original_url=data["original_url"],
                            category=data.get("category"),
                            impact_score=0.0,
                            is_breaking=False,
                            status=ArticleStatusEnum.pending_normal,
                            published_at=data.get("published_at"),
                        )
                        db.add(article)
                        await db.commit()
                        total_nuevos += 1
                        logger.info("✅ Artículo guardado: %s", data.get("title", "")[:60])

                        # Agregar a lista de recientes
                        articulos_recientes_dicts.append({
                            "source_id": data["source_id"],
                            "title": data["title"],
                            "content": data.get("content", ""),
                            "published_at": data.get("published_at"),
                            "original_url": data["original_url"],
                        })
                        
                        # Verificar si es breaking news después de guardar
                        score_final = scorer.score(data, articulos_recientes_dicts[:-1])
                        if score_final >= 80:
                            article.is_breaking = True
                            article.status = ArticleStatusEnum.pending_breaking
                            article.impact_score = score_final
                            await db.commit()
                            logger.info("🔥 BREAKING NEWS: %s (score: %.2f)", data.get("title", "")[:60], score_final)
                        else:
                            article.impact_score = score_final
                            await db.commit()

                except Exception as e:
                    logger.error(
                        "Error procesando artículo de '%s': %s",
                        fuente.name, e,
                    )
                    # Rollback automático por el context manager
                    continue
            
            logger.info(
                "Fuente %s: %d artículos nuevos guardados",
                fuente.name, total_nuevos
            )
        
        except Exception as e:
            logger.error(
                "Error scrapeando fuente '%s' (ID %d): %s",
                fuente.name, fuente.id, e,
            )
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # Log final del job
    logger.info(
        "scraping_job completado: %d artículos nuevos guardados de %d fuentes",
        total_nuevos, len(fuentes),
    )
    
    # Guardar log de actividad en la base de datos
    try:
        async with get_session_maker() as db_log:
            log_entry = ActivityLog(
                action="scraping_job",
                result="success",
                detail=f"{total_nuevos} artículos nuevos encontrados. {len(fuentes)} fuentes procesadas."
            )
            db_log.add(log_entry)
            await db_log.commit()
    except Exception as log_error:
        logger.error(f"Error guardando log: {log_error}")


# ─── Job 2: Limpieza ─────────────────────────────────────────────────────────

async def cleanup_job():
    """
    Elimina artículos antiguos:
      - Descartados de más de 48 horas
      - Publicados de más de 7 días
    """
    logger.info("Iniciando cleanup_job...")
    async with get_session_maker() as db:
        try:
            ahora = datetime.utcnow()

            # Eliminar descartados de más de 48h
            limite_descartados = ahora - timedelta(hours=48)
            result_desc = await db.execute(
                delete(Article).where(
                    Article.status == ArticleStatusEnum.discarded,
                    Article.created_at < limite_descartados,
                )
            )
            eliminados_descartados = result_desc.rowcount

            # Eliminar publicados de más de 7 días
            limite_publicados = ahora - timedelta(days=7)
            result_pub = await db.execute(
                delete(Article).where(
                    Article.status == ArticleStatusEnum.published,
                    Article.published_at < limite_publicados,
                )
            )
            eliminados_publicados = result_pub.rowcount

            await db.commit()
            logger.info(
                "cleanup_job completado: %d descartados y %d publicados eliminados",
                eliminados_descartados, eliminados_publicados,
            )

        except Exception as e:
            logger.error("Error en cleanup_job: %s", e)
            await db.rollback()


# ─── Inicialización ──────────────────────────────────────────────────────────

def start_scheduler():
    """Configura e inicia el planificador."""
    scheduler.add_job(
        scraping_job,
        "interval",
        minutes=SCRAPING_INTERVAL_MINUTOS,
        id="scraping_job",
        replace_existing=True,
    )
    scheduler.add_job(
        cleanup_job,
        "interval",
        hours=CLEANUP_INTERVAL_HORAS,
        id="cleanup_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler iniciado: scraping cada %d min, cleanup cada %d h",
        SCRAPING_INTERVAL_MINUTOS, CLEANUP_INTERVAL_HORAS,
    )


def stop_scheduler():
    """Detiene el planificador."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido.")


async def execute_scraping(client_id: Optional[int] = None, max_sources: int = 10, limit: int = 5) -> int:
    """
    Función exportable para ejecutar scraping bajo demanda desde la API.
    
    Args:
        client_id: ID del cliente que solicita el scraping (None = todas las fuentes)
        max_sources: Número máximo de fuentes a procesar
        limit: Límite de artículos por fuente
        
    Returns:
        int: Número de artículos nuevos obtenidos
    """
    logger.info("Ejecutando scraping bajo demanda para cliente %s (max_sources=%d, limit=%d)", 
                client_id, max_sources, limit)
    
    # Obtener fuentes activas
    async with get_session_maker() as db:
        query = select(Source).where(Source.is_active.is_(True))
        
        # Si se especifica client_id, filtrar sources del cliente
        # Por ahora, procesamos todas las fuentes activas
        
        result = await db.execute(query)
        fuentes = result.scalars().all()
        
        # Limitar número de fuentes según plan
        if len(fuentes) > max_sources:
            fuentes = fuentes[:max_sources]
        
        if not fuentes:
            logger.info("No hay fuentes activas disponibles")
            return 0
        
        # Obtener artículos recientes para deduplicación
        hace_2h = datetime.utcnow() - timedelta(hours=2)
        result_recent = await db.execute(
            select(Article).where(Article.created_at >= hace_2h)
        )
        articulos_recientes = result_recent.scalars().all()
    
    # Convertir URLs recientes para deduplicación
    urls_existentes = {a.original_url for a in articulos_recientes if a.original_url}
    
    total_nuevos = 0
    
    # Procesar cada fuente
    for fuente in fuentes:
        try:
            # Obtener perfil de la fuente
            async with get_session_maker() as db:
                result_profile = await db.execute(
                    select(SourceProfile).where(SourceProfile.source_id == fuente.id)
                )
                profile = result_profile.scalar_one_or_none()
                profile_dict = None
                
                if profile and profile.confidence_score >= MIN_CONFIDENCE_FOR_PROFILER:
                    profile_dict = {
                        "title_selector": profile.title_selector,
                        "body_selector": profile.body_selector,
                        "image_selector": profile.image_selector,
                        "date_selector": profile.date_selector,
                        "author_selector": profile.author_selector,
                        "confidence_score": profile.confidence_score,
                    }
            
            # Hacer scraping de la fuente con auto-profiling
            articles_data, nuevo_perfil = await fetch_rss(fuente, profile_dict, limit=limit)
            
            # Guardar el nuevo perfil si se aprendió automáticamente
            if nuevo_perfil:
                async with get_session_maker() as db_prof:
                    try:
                        stmt = select(SourceProfile).where(SourceProfile.source_id == fuente.id)
                        res = await db_prof.execute(stmt)
                        profile_obj = res.scalar_one_or_none()
                        if not profile_obj:
                            new_profile = SourceProfile(
                                source_id=fuente.id,
                                **nuevo_perfil,
                                last_verified=datetime.utcnow()
                            )
                            db_prof.add(new_profile)
                            await db_prof.commit()
                            logger.info("🤖 Perfil aprendido guardado para %s", fuente.name)
                    except Exception:
                        pass
            
            if not articles_data:
                continue
            
            # Guardar artículos nuevos
            for data in articles_data:
                # Verificar duplicado
                if data.get("original_url") in urls_existentes:
                    continue
                
                # Guardar artículo
                async with get_session_maker() as db:
                    article = Article(
                        source_id=fuente.id,
                        title=data["title"],
                        content=data["content"],
                        excerpt=data.get("excerpt", ""),
                        image_url=data.get("image_url"),
                        original_url=data["original_url"],
                        category=data.get("category"),
                        impact_score=0.0,
                        is_breaking=False,
                        status=ArticleStatusEnum.pending_normal,
                        published_at=data.get("published_at"),
                    )
                    db.add(article)
                    await db.commit()
                    total_nuevos += 1
                    urls_existentes.add(data["original_url"])
                    
                    logger.info("✅ Artículo obtenido: %s", data.get("title", "")[:60])
                    
                    # Si llegamos al límite, detener
                    if total_nuevos >= limit:
                        break
            
            if total_nuevos >= limit:
                break
                
        except Exception as e:
            logger.error("Error procesando fuente %s: %s", fuente.name, str(e))
            continue
    
    logger.info("Scraping bajo demanda completado: %d artículos nuevos", total_nuevos)
    return total_nuevos
