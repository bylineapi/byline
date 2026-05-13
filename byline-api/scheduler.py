# scheduler.py - Programador de tareas con APScheduler para scraping y limpieza

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session_maker
from models import Source, Article, ArticleStatusEnum, SourceProfile
from scraper import fetch_rss, MIN_CONFIDENCE_FOR_PROFILER
from scorer import ImpactScorer

logger = logging.getLogger(__name__)

# Intervalos en minutos
SCRAPING_INTERVAL_MINUTOS = 15
CLEANUP_INTERVAL_HORAS = 24

scheduler = AsyncIOScheduler()
scorer = ImpactScorer()


# ─── Job 1: Scraping ─────────────────────────────────────────────────────────

async def scraping_job():
    """
    Itera todas las fuentes activas, obtiene artículos nuevos via RSS,
    los puntúa y guarda en BD los que no sean 'discarded'.
    """
    logger.info("Iniciando scraping_job...")
    session_maker = get_session_maker()
    async with session_maker() as db:
        try:
            # Obtener fuentes activas
            result = await db.execute(
                select(Source).where(Source.is_active.is_(True))
            )
            fuentes = result.scalars().all()

            if not fuentes:
                logger.info("No hay fuentes activas para scrapear.")
                return

            # Obtener artículos de las últimas 2 horas para el trending
            hace_2h = datetime.utcnow() - timedelta(hours=2)
            result_recent = await db.execute(
                select(Article).where(Article.created_at >= hace_2h)
            )
            articulos_recientes = result_recent.scalars().all()

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

            for fuente in fuentes:
                # Obtener perfil de scraping de la fuente
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

                try:
                    articulos_crudos = await fetch_rss(fuente, profile_dict)
                except Exception as e:
                    logger.error(
                        "Error scrapeando fuente '%s' (ID %d): %s",
                        fuente.name, fuente.id, e,
                    )
                    continue

                for data in articulos_crudos:
                    try:
                        # Verificar si ya existe por original_url
                        existe = await db.execute(
                            select(Article).where(
                                Article.original_url == data["original_url"]
                            )
                        )
                        if existe.scalar_one_or_none():
                            continue

                        # Puntuar
                        score_final = scorer.score(data, articulos_recientes_dicts)
                        data["impact_score"] = score_final

                        # Asignar estado según score
                        if score_final >= 80:
                            data["is_breaking"] = True
                            data["status"] = ArticleStatusEnum.pending_breaking
                        elif score_final >= 40:
                            data["status"] = ArticleStatusEnum.pending_normal
                        else:
                            data["status"] = ArticleStatusEnum.discarded

                        # Guardar solo no descartados
                        if data["status"] != ArticleStatusEnum.discarded:
                            article = Article(
                                source_id=data["source_id"],
                                title=data["title"],
                                content=data["content"],
                                excerpt=data.get("excerpt", ""),
                                image_url=data.get("image_url"),
                                original_url=data["original_url"],
                                category=data.get("category"),
                                impact_score=data["impact_score"],
                                is_breaking=data["is_breaking"],
                                status=data["status"],
                                published_at=data.get("published_at"),
                            )
                            db.add(article)
                            total_nuevos += 1

                            # Agregar a lista de recientes para próximos scores
                            articulos_recientes_dicts.append({
                                "source_id": data["source_id"],
                                "title": data["title"],
                                "content": data["content"],
                                "published_at": data.get("published_at"),
                            })

                    except Exception as e:
                        logger.error(
                            "Error procesando artículo de '%s': %s",
                            fuente.name, e,
                        )
                        continue

            await db.commit()
            logger.info(
                "scraping_job completado: %d artículos nuevos guardados de %d fuentes",
                total_nuevos, len(fuentes),
            )

        except Exception as e:
            logger.error("Error en scraping_job: %s", e)
            await db.rollback()


# ─── Job 2: Limpieza ─────────────────────────────────────────────────────────

async def cleanup_job():
    """
    Elimina artículos antiguos:
      - Descartados de más de 48 horas
      - Publicados de más de 7 días
    """
    logger.info("Iniciando cleanup_job...")
    session_maker = get_session_maker()
    async with session_maker() as db:
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
