# main.py - Punto de entrada de la API FastAPI para distribución de noticias

import os
import secrets
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text, delete
from sqlalchemy.orm import joinedload

from database import get_db, init_db
from models import (
    Client, Source, Article, ClientArticle, SourceProfile,
    PlanEnum, ArticleStatusEnum, ActivityLog,
)
from schemas import (
    HealthOut, ClientCreate, ClientOut, ClientList,
    ClientUpdate, ClientUpdateOut, StatsOut, LogOut, ArticleListItem,
    SourceCreate, SourceOut, ArticleOut,
    SourceProfileOut, AnalyzeHTMLIn, AnalyzeProfileOut,
    VerifyProfileOut, SampleExtraction,
)
from auth import (
    get_current_client, verify_admin_secret,
    hash_api_key, SUSCRIPTION_PLANS,
)
from scheduler import start_scheduler, stop_scheduler, scraping_job
from profiler import HTMLProfiler
from category_detector import detectar_categoria_desde_feed, obtener_nombre_desde_feed
from keep_alive import set_api_url, start_keep_alive, stop_keep_alive

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa BD y scheduler al arrancar; limpia al detener."""
    keep_alive_task = None
    try:
        logger.info("Iniciando aplicación...")
        logger.info(f"DATABASE_URL configurada: {'Sí' if os.getenv('DATABASE_URL') else 'NO — FALTA'}")
        logger.info(f"ADMIN_SECRET configurado: {'Sí' if os.getenv('ADMIN_SECRET') else 'NO — FALTA'}")
        
        await init_db()
        logger.info("Base de datos inicializada correctamente")
        
        start_scheduler()
        logger.info("Scheduler iniciado correctamente")
        
        # Configurar keep-alive para Render
        api_url = os.getenv("RENDER_EXTERNAL_URL", "https://byline-dgpt.onrender.com")
        set_api_url(api_url)
        keep_alive_task = start_keep_alive()
        logger.info(f"Keep-alive configurado: {api_url}")
        
        yield
    except Exception as e:
        logger.error(f"ERROR CRÍTICO AL INICIAR: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        from database import engine
        stop_scheduler()
        stop_keep_alive(keep_alive_task)
        await engine.dispose()
        logger.info("Aplicación cerrada correctamente")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Byline API",
    description="Byline — Sistema de distribución de noticias para múltiples clientes",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Endpoint de verificación de salud del servicio y conexión a Neon."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "detail": str(e)
            }
        )


@app.get("/ping")
async def ping():
    """
    Endpoint público para keep-alive de Render.
    Render free tier se duerme después de 15 min de inactividad.
    Este endpoint permite hacer ping cada 12 min para mantenerlo activo.
    """
    return {
        "status": "ok",
        "message": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }


# ─── Admin: Clientes ─────────────────────────────────────────────────────────

@app.post("/admin/clients", response_model=ClientOut)
async def create_client(
    data: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Crea un nuevo cliente con una API key generada automáticamente."""
    raw_key = secrets.token_urlsafe(32)
    hashed = hash_api_key(raw_key)

    client = Client(
        name=data.name,
        api_key=hashed,
        plan=PlanEnum(data.plan),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    return ClientOut(
        id=client.id,
        name=client.name,
        plan=client.plan.value,
        is_active=client.is_active,
        created_at=client.created_at,
        api_key=raw_key,
    )


@app.get("/admin/clients", response_model=list[ClientList])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Lista todos los clientes registrados."""
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    clients = result.scalars().all()
    return [
        ClientList(
            id=c.id,
            name=c.name,
            plan=c.plan.value,
            is_active=c.is_active,
            created_at=c.created_at,
        )
    for c in clients
    ]


@app.get("/admin/clients/verify", response_model=ClientList)
async def verify_client(
    api_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Verifica el plan de un cliente por su API Key."""
    from auth import verify_api_key

    result = await db.execute(select(Client))
    clients = result.scalars().all()

    for client in clients:
        if verify_api_key(api_key, client.api_key):
            return ClientList(
                id=client.id,
                name=client.name,
                plan=client.plan.value,
                is_active=client.is_active,
                created_at=client.created_at,
            )

    raise HTTPException(status_code=404, detail="Cliente no encontrado")


@app.patch("/admin/clients/{client_id}", response_model=ClientUpdateOut)
async def update_client(
    client_id: int,
    data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Actualiza un cliente existente (partial update).
    Solo actualiza los campos que se envíen en el body.
    """
    # Buscar cliente
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Actualizar solo los campos presentes
    if data.name is not None:
        client.name = data.name
    
    if data.plan is not None:
        # Validar que el plan sea válido
        if data.plan not in ["basic", "pro", "business"]:
            raise HTTPException(
                status_code=400,
                detail="Plan inválido. Debe ser: basic, pro o business"
            )
        client.plan = PlanEnum(data.plan)
    
    if data.is_active is not None:
        client.is_active = data.is_active
    
    await db.commit()
    await db.refresh(client)
    
    return ClientUpdateOut(
        id=client.id,
        name=client.name,
        plan=client.plan.value,
        is_active=client.is_active,
        created_at=client.created_at,
    )





# ─── Admin: Fuentes RSS (continuación) ───────────────────────────────────────

profiler = HTMLProfiler()


# ─── Admin: Fuentes RSS ──────────────────────────────────────────────────────

@app.post("/admin/sources", response_model=SourceOut)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Agrega una nueva fuente RSS."""
    source = Source(
        name=data.name,
        url=data.url,
        rss_url=data.rss_url,
        category=data.category,
        favicon_url=data.favicon_url,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return SourceOut.model_validate(source)


@app.post("/admin/sources/bulk", response_model=dict)
async def create_sources_bulk(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Agrega múltiples fuentes RSS en lote.
    Detecta automáticamente nombre y categoría de cada fuente.
    
    Body esperado:
    {
        "rss_urls": [
            "https://feeds.elpais.com/rss/tecnologia.xml",
            "https://feeds.elpais.com/rss/deportes.xml"
        ]
    }
    
    Retorna:
    {
        "success": true,
        "total": 10,
        "created": 8,
        "failed": 2,
        "sources": [...],
        "errors": [...]
    }
    """
    rss_urls = data.get("rss_urls", [])
    
    if not rss_urls or not isinstance(rss_urls, list):
        raise HTTPException(
            status_code=400,
            detail="Se requiere una lista de URLs RSS en 'rss_urls'"
        )
    
    results = {
        "success": True,
        "total": len(rss_urls),
        "created": 0,
        "failed": 0,
        "sources": [],
        "errors": []
    }
    
    for rss_url in rss_urls:
        rss_url = rss_url.strip()
        if not rss_url:
            continue
        
        try:
            # Verificar si ya existe
            result = await db.execute(
                select(Source).where(Source.rss_url == rss_url)
            )
            existente = result.scalar_one_or_none()
            
            if existente:
                results["failed"] += 1
                results["errors"].append({
                    "url": rss_url,
                    "error": "La fuente ya existe"
                })
                continue
            
            # Detectar categoría automáticamente
            category = detectar_categoria_desde_feed(rss_url)
            
            # Obtener nombre automáticamente
            name = obtener_nombre_desde_feed(rss_url)
            
            if not name:
                # Fallback: usar el dominio como nombre
                from urllib.parse import urlparse
                domain = urlparse(rss_url).netloc.replace("www.", "")
                name = domain.split(".")[0].title()
            
            # Crear la fuente
            source = Source(
                name=name,
                rss_url=rss_url,
                category=category,
            )
            db.add(source)
            await db.flush()
            await db.refresh(source)
            
            results["created"] += 1
            results["sources"].append({
                "id": source.id,
                "name": source.name,
                "rss_url": source.rss_url,
                "category": source.category
            })
            
            logger.info(
                "Fuente creada automáticamente: %s (categoría: %s)",
                name, category or "sin categorizar"
            )
            
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({
                "url": rss_url,
                "error": str(e)
            })
            logger.error("Error creando fuente %s: %s", rss_url, e)
    
    await db.commit()
    
    if results["failed"] > 0 and results["created"] == 0:
        results["success"] = False
    
    return results


@app.get("/admin/sources", response_model=list[SourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Lista todas las fuentes RSS registradas."""
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    sources = result.scalars().all()
    return [SourceOut.model_validate(s) for s in sources]


@app.post("/admin/sources/check-health", response_model=dict)
async def check_sources_health(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Verifica el estado de todas las fuentes RSS.
    Retorna cuáles están funcionando y cuáles están caídas.
    """
    import feedparser
    import asyncio
    
    result = await db.execute(select(Source).where(Source.is_active.is_(True)))
    sources = result.scalars().all()
    
    health_status = {
        "total": len(sources),
        "healthy": 0,
        "unhealthy": 0,
        "sources": []
    }
    
    async def check_source(source: Source):
        """Verifica una fuente individual."""
        try:
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(
                None,
                lambda: feedparser.parse(source.rss_url)
            )
            
            is_healthy = not feed.bozo or (feed.bozo and len(feed.entries) > 0)
            
            return {
                "id": source.id,
                "name": source.name,
                "rss_url": source.rss_url,
                "healthy": is_healthy,
                "entries_found": len(feed.entries),
                "error": str(feed.bozo_exception) if feed.bozo else None
            }
        except Exception as e:
            return {
                "id": source.id,
                "name": source.name,
                "rss_url": source.rss_url,
                "healthy": False,
                "entries_found": 0,
                "error": str(e)
            }
    
    # Verificar todas las fuentes en paralelo
    tasks = [check_source(source) for source in sources]
    results = await asyncio.gather(*tasks)
    
    for result in results:
        health_status["sources"].append(result)
        if result["healthy"]:
            health_status["healthy"] += 1
        else:
            health_status["unhealthy"] += 1
    
    return health_status


@app.delete("/admin/sources/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Elimina una fuente completamente de la base de datos.
    También elimina todos los artículos asociados a esta fuente.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    
    # Eliminar artículos asociados
    await db.execute(delete(Article).where(Article.source_id == source_id))
    
    # Eliminar perfil de scraping si existe
    await db.execute(delete(SourceProfile).where(SourceProfile.source_id == source_id))
    
    # Eliminar la fuente
    await db.delete(source)
    await db.commit()
    
    return {"success": True, "message": "Fuente eliminada completamente"}


@app.patch("/admin/sources/{source_id}")
async def update_source(
    source_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Actualiza una fuente existente.
    Permite reactivar fuentes desactivadas.
    """
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Fuente no encontrada")
    
    # Actualizar campos permitidos
    if "is_active" in data:
        source.is_active = data["is_active"]
    
    if "name" in data:
        source.name = data["name"]
    
    if "category" in data:
        source.category = data["category"]
    
    if "rss_url" in data:
        source.rss_url = data["rss_url"]
    
    await db.commit()
    await db.refresh(source)
    
    return {
        "success": True,
        "source": {
            "id": source.id,
            "name": source.name,
            "rss_url": source.rss_url,
            "category": source.category,
            "is_active": source.is_active
        }
    }


# ─── News ─────────────────────────────────────────────────────────────────────

@app.get("/news", response_model=list[ArticleOut])
async def get_news(
    category: Optional[str] = Query(None),
    only_breaking: bool = Query(False),
    limit: Optional[int] = Query(None),
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    """
    Obtiene noticias según el plan del cliente.

    - category: filtrar por categoría
    - only_breaking: solo noticias de último momento
    - limit: máximo de resultados (respetando el límite del plan)
    """
    plan = SUSCRIPTION_PLANS[client.plan.value]

    # Si pide breaking pero el plan no lo incluye
    if only_breaking and not plan["breaking_news"]:
        raise HTTPException(
            status_code=403,
            detail="Tu plan no incluye noticias de último momento",
        )

    # Construir query
    statuses = [
        ArticleStatusEnum.pending_normal,
        ArticleStatusEnum.pending_breaking,
    ]
    if only_breaking:
        statuses = [ArticleStatusEnum.pending_breaking]

    query = (
        select(Article)
        .options(joinedload(Article.source))  # Carga la relación source para evitar N+1
        .where(Article.status.in_(statuses))
        .order_by(desc(Article.impact_score), desc(Article.created_at))
    )

    if category:
        query = query.where(Article.category == category)

    # Aplicar límite según plan
    max_limit = plan["posts_per_category_hour"]
    actual_limit = min(limit, max_limit) if limit else max_limit
    query = query.limit(actual_limit)

    result = await db.execute(query)
    articulos = result.scalars().all()

    # Marcar artículos entregados en client_articles para tracking
    await _marcar_articulos_entregados(db, client.id, articulos)

    # Si el plan no incluye contenido completo, ocultarlo
    if not plan["full_content"]:
        for a in articulos:
            a.content = None

    return [ArticleOut.model_validate(a) for a in articulos]


@app.get("/news/breaking", response_model=list[ArticleOut])
async def get_breaking_news(
    client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene solo noticias breaking."""
    plan = SUSCRIPTION_PLANS[client.plan.value]

    if not plan["breaking_news"]:
        raise HTTPException(
            status_code=403,
            detail="Tu plan no incluye noticias de último momento",
        )

    query = (
        select(Article)
        .options(joinedload(Article.source))  # Carga la relación source para evitar N+1
        .where(Article.status == ArticleStatusEnum.pending_breaking)
        .order_by(desc(Article.impact_score), desc(Article.created_at))
        .limit(plan["posts_per_category_hour"])
    )

    result = await db.execute(query)
    articulos = result.scalars().all()

    await _marcar_articulos_entregados(db, client.id, articulos)

    if not plan["full_content"]:
        for a in articulos:
            a.content = None

    return [ArticleOut.model_validate(a) for a in articulos]


# ─── Source Profiler: Analizar HTML ──────────────────────────────────────────

@app.post("/admin/sources/analyze-html", response_model=AnalyzeProfileOut)
async def analyze_html_source(
    data: AnalyzeHTMLIn,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Analiza código HTML de una fuente y detecta automáticamente
    los selectores CSS necesarios para extraer contenido.

    Si confidence_score >= 0.7, guarda source + profile automáticamente.
    Si confidence_score < 0.7, retorna warning para revisión manual.
    """
    # Analizar el HTML recibido
    analisis = profiler.analyze(data.html, data.source_url)
    confidence = analisis["confidence_score"]

    warning = None
    source_id = None

    # Guardar fuente y perfil si la confianza es suficiente
    if confidence >= 0.7:
        # Verificar si la fuente ya existe por RSS o URL
        result = await db.execute(
            select(Source).where(Source.url == data.source_url)
        )
        fuente_existente = result.scalar_one_or_none()

        if fuente_existente:
            source_id = fuente_existente.id
        else:
            # Crear nueva fuente (sin RSS ya que es HTML only)
            nueva_fuente = Source(
                name=data.source_name,
                url=data.source_url,
                rss_url="",  # HTML-only source
                category=data.category,
            )
            db.add(nueva_fuente)
            await db.flush()
            source_id = nueva_fuente.id

        # Crear perfil de scraping
        perfil = SourceProfile(
            source_id=source_id,
            title_selector=analisis.get("title_selector"),
            body_selector=analisis.get("body_selector"),
            image_selector=analisis.get("image_selector"),
            date_selector=analisis.get("date_selector"),
            author_selector=analisis.get("author_selector"),
            confidence_score=confidence,
            last_verified=datetime.utcnow(),
        )
        db.add(perfil)
        await db.commit()
    else:
        warning = (
            f"La confianza del perfil es {confidence:.0%}. "
            "Revisa los selectores manualmente antes de usar este perfil en producción."
        )

    return AnalyzeProfileOut(
        title_selector=analisis.get("title_selector"),
        body_selector=analisis.get("body_selector"),
        image_selector=analisis.get("image_selector"),
        date_selector=analisis.get("date_selector"),
        author_selector=analisis.get("author_selector"),
        confidence_score=confidence,
        sample_extraction=SampleExtraction(**analisis.get("sample_extraction", {})),
        warning=warning,
        source_id=source_id,
    )


@app.get("/admin/sources/{source_id}/profile", response_model=SourceProfileOut)
async def get_source_profile(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Retorna el perfil actual de scraping de una fuente."""
    result = await db.execute(
        select(SourceProfile).where(SourceProfile.source_id == source_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Esta fuente no tiene un perfil de scraping configurado.",
        )

    return SourceProfileOut.model_validate(profile)


@app.post("/admin/sources/{source_id}/verify-profile", response_model=VerifyProfileOut)
async def verify_source_profile(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Descarga la URL principal de la fuente y verifica si el perfil
    de scraping sigue funcionando correctamente.
    """
    # Obtener fuente y su perfil
    result_source = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result_source.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Fuente no encontrada.")

    result_profile = await db.execute(
        select(SourceProfile).where(SourceProfile.source_id == source_id)
    )
    profile = result_profile.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Esta fuente no tiene un perfil de scraping configurado.",
        )

    # Construir diccionario de selectores desde el perfil
    profile_dict = {
        "title_selector": profile.title_selector,
        "body_selector": profile.body_selector,
        "image_selector": profile.image_selector,
        "date_selector": profile.date_selector,
        "author_selector": profile.author_selector,
    }

    # Descargar y extraer con el profiler
    extraccion = profiler.extract(source.url, profile_dict)

    success = bool(extraccion.get("title") and extraccion.get("body"))
    mensaje = "El perfil funciona correctamente." if success else "La extracción falló. Considera re-analizar."

    # Actualizar last_verified
    profile.last_verified = datetime.utcnow()
    await db.commit()

    # Preparar preview del cuerpo (primeros 200 chars)
    body_preview = None
    if extraccion.get("body"):
        body_preview = extraccion["body"][:200] + "..." if len(extraccion["body"]) > 200 else extraccion["body"]

    return VerifyProfileOut(
        success=success,
        title=extraccion.get("title"),
        body_preview=body_preview,
        message=mensaje,
        last_verified=datetime.utcnow(),
    )


# ─── Admin: Stats ─────────────────────────────────────────────────────────────

@app.get("/admin/stats", response_model=StatsOut)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Retorna métricas del día actual (desde medianoche).
    """
    # Obtener la fecha de hoy a medianoche
    hoy = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Artículos de hoy (todos los statuses)
    result_articles_today = await db.execute(
        select(Article).where(Article.created_at >= hoy)
    )
    articles_today = len(result_articles_today.scalars().all())
    
    # Breaking news de hoy
    result_breaking = await db.execute(
        select(Article).where(
            Article.created_at >= hoy,
            Article.is_breaking.is_(True)
        )
    )
    breaking_today = len(result_breaking.scalars().all())
    
    # Fuentes activas
    result_sources = await db.execute(
        select(Source).where(Source.is_active.is_(True))
    )
    active_sources = len(result_sources.scalars().all())
    
    # Total de clientes
    result_total_clients = await db.execute(select(Client))
    total_clients = len(result_total_clients.scalars().all())
    
    # Clientes activos
    result_active_clients = await db.execute(
        select(Client).where(Client.is_active.is_(True))
    )
    active_clients = len(result_active_clients.scalars().all())
    
    # Artículos descartados hoy
    result_discarded = await db.execute(
        select(Article).where(
            Article.created_at >= hoy,
            Article.status == ArticleStatusEnum.discarded
        )
    )
    articles_discarded_today = len(result_discarded.scalars().all())
    
    return StatsOut(
        articles_today=articles_today,
        breaking_today=breaking_today,
        active_sources=active_sources,
        total_clients=total_clients,
        active_clients=active_clients,
        articles_discarded_today=articles_discarded_today,
    )


@app.post("/admin/scrape", response_model=dict)
async def trigger_manual_scrape(
    test_date: Optional[str] = Query(None, description="Fecha para pruebas (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Ejecuta el scraping de forma manual.
    Útil para probar nuevas fuentes o forzar la extracción de artículos.
    
    Args:
        test_date: Fecha opcional en formato YYYY-MM-DD para pruebas
    """
    try:
        logger.info("🔧 Scraping manual iniciado por admin")
        
        # Parsear fecha de prueba si se proporciona
        force_date = None
        if test_date:
            try:
                force_date = datetime.strptime(test_date, "%Y-%m-%d").replace(hour=12, minute=0, second=0)
                logger.info(f"📅 Usando fecha de prueba: {force_date}")
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
        # Ejecutar el job de scraping (maneja su propia sesión internamente)
        try:
            await scraping_job(force_date)
            logger.info("✅ scraping_job completado")
        except Exception as scrape_error:
            logger.error(f"Error en scraping_job: {scrape_error}")
            # No lanzar error aquí, continuar para obtener estadísticas
        
        # Crear una nueva sesión para obtener estadísticas
        from database import get_session_maker
        session_maker = get_session_maker()
        
        articles_today = 0
        active_sources = 0
        
        try:
            async with session_maker() as new_db:
                # Contar artículos nuevos creados hoy
                hoy = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                result = await new_db.execute(
                    select(Article).where(Article.created_at >= hoy)
                )
                articles_today = len(result.scalars().all())
                
                # Contar fuentes activas procesadas
                result_sources = await new_db.execute(
                    select(Source).where(Source.is_active.is_(True))
                )
                active_sources = len(result_sources.scalars().all())
        except Exception as stats_error:
            logger.error(f"Error obteniendo estadísticas: {stats_error}")
        
        return {
            "success": True,
            "message": "Scraping ejecutado. Revisa los logs para detalles.",
            "articles_today": articles_today,
            "sources_processed": active_sources,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error crítico en scraping manual: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Incluso en caso de error crítico, intentar devolver estadísticas
        try:
            from database import get_session_maker
            session_maker = get_session_maker()
            async with session_maker() as new_db:
                hoy = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                result = await new_db.execute(
                    select(Article).where(Article.created_at >= hoy)
                )
                articles_today = len(result.scalars().all())
                
                result_sources = await new_db.execute(
                    select(Source).where(Source.is_active.is_(True))
                )
                active_sources = len(result_sources.scalars().all())
                
                return {
                    "success": False,
                    "message": f"Error ejecutando scraping: {str(e)}",
                    "articles_today": articles_today,
                    "sources_processed": active_sources,
                    "timestamp": datetime.utcnow().isoformat()
                }
        except:
            pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando scraping: {str(e)}"
        )


# ─── Admin: Logs ─────────────────────────────────────────────────────────────

@app.get("/admin/logs", response_model=list[LogOut])
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Retorna entradas de activity_logs.
    """
    result = await db.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    logs = result.scalars().all()
    return [LogOut.model_validate(log) for log in logs]


# ─── Admin: Articles ─────────────────────────────────────────────────────────

@app.get("/admin/articles", response_model=list[ArticleListItem])
async def get_admin_articles(
    category: Optional[str] = Query(None),
    is_breaking: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """
    Retorna artículos con filtros opcionales.
    Incluye datos de la fuente (source.name) en la respuesta.
    """
    # Construir query con filtros
    query = (
        select(Article)
        .options(joinedload(Article.source))
        .order_by(Article.created_at.desc())
    )
    
    if category:
        query = query.where(Article.category == category)
    
    if is_breaking is not None:
        query = query.where(Article.is_breaking == is_breaking)
    
    if status:
        query = query.where(Article.status == status)
    
    # Aplicar paginación
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    articles = result.scalars().all()
    
    # Mapear artículos con nombre de fuente
    return [
        ArticleListItem(
            id=a.id,
            source_name=a.source.name if a.source else "Desconocida",
            title=a.title,
            category=a.category,
            impact_score=a.impact_score,
            is_breaking=a.is_breaking,
            status=a.status.value if a.status else "unknown",
            created_at=a.created_at,
        )
        for a in articles
    ]


# ─── Admin Panel HTML ─────────────────────────────────────────────────────────

@app.get("/admin/panel", response_class=HTMLResponse)
async def admin_panel():
    """Sirve el panel de administración HTML."""
    html_path = "admin_panel/index.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<html><body><h1>Panel no encontrado</h1></body></html>",
            status_code=404,
        )


# ─── Helper ──────────────────────────────────────────────────────────────────

async def _marcar_articulos_entregados(
    db: AsyncSession,
    client_id: int,
    articulos: list[Article],
):
    """Registra en client_articles qué artículos fueron entregados al cliente."""
    ahora = datetime.utcnow()
    for article in articulos:
        existe = await db.execute(
            select(ClientArticle).where(
                ClientArticle.client_id == client_id,
                ClientArticle.article_id == article.id,
            )
        )
        if not existe.scalar_one_or_none():
            db.add(ClientArticle(
                client_id=client_id,
                article_id=article.id,
                published_at=ahora,
            ))
    await db.commit()
