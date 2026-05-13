# main.py - Punto de entrada de la API FastAPI para distribución de noticias

import secrets
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from database import get_db, init_db
from models import (
    Client, Source, Article, ClientArticle, SourceProfile,
    PlanEnum, ArticleStatusEnum,
)
from schemas import (
    HealthOut, ClientCreate, ClientOut, ClientList,
    SourceCreate, SourceOut, ArticleOut,
    SourceProfileOut, AnalyzeHTMLIn, AnalyzeProfileOut,
    VerifyProfileOut, SampleExtraction,
)
from auth import (
    get_current_client, verify_admin_secret,
    hash_api_key, SUSCRIPTION_PLANS,
)
from scheduler import start_scheduler, stop_scheduler
from profiler import HTMLProfiler

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
    logger.info("Iniciando aplicación...")
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Aplicación detenida.")


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

@app.get("/health", response_model=HealthOut)
async def health():
    """Endpoint de verificación de salud del servicio."""
    return HealthOut(status="ok")


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


# ─── Inicialización del profiler global ──────────────────────────────────────

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


@app.get("/admin/sources", response_model=list[SourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin_secret),
):
    """Lista todas las fuentes RSS registradas."""
    result = await db.execute(select(Source).order_by(Source.created_at.desc()))
    sources = result.scalars().all()
    return [SourceOut.model_validate(s) for s in sources]


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
