# schemas.py - Esquemas Pydantic v2 para request/response

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─── Plan ─────────────────────────────────────────────────────────────────────

class PlanInfo(BaseModel):
    max_sources: int
    posts_per_category_hour: int
    breaking_news: bool
    full_content: bool
    ai_summary: bool


# ─── Client ───────────────────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    plan: str = Field(default="basic", pattern=r"^(basic|pro|business)$")


class ClientOut(BaseModel):
    id: int
    name: str
    plan: str
    is_active: bool
    created_at: datetime
    api_key: Optional[str] = None  # solo se muestra al crear

    model_config = {"from_attributes": True}


class ClientList(BaseModel):
    id: int
    name: str
    plan: str
    is_active: bool
    created_at: datetime
    api_key: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Source ───────────────────────────────────────────────────────────────────

class SourceBasic(BaseModel):
    """Schema básico de fuente para incluir en respuestas de artículos."""
    id: int
    name: str
    url: Optional[str] = None
    favicon_url: Optional[str] = None

    model_config = {"from_attributes": True}


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: Optional[str] = None
    rss_url: str = Field(..., max_length=500)
    category: Optional[str] = None
    favicon_url: Optional[str] = None


class SourceOut(BaseModel):
    id: int
    name: str
    url: Optional[str]
    rss_url: str
    category: Optional[str]
    favicon_url: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Source Profile (Source Profiler) ─────────────────────────────────────────

class SourceProfileOut(BaseModel):
    id: int
    source_id: int
    title_selector: Optional[str]
    body_selector: Optional[str]
    image_selector: Optional[str]
    date_selector: Optional[str]
    author_selector: Optional[str]
    confidence_score: float
    last_verified: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SampleExtraction(BaseModel):
    title: Optional[str] = None
    image_url: Optional[str] = None
    date: Optional[str] = None


class AnalyzeProfileOut(BaseModel):
    title_selector: Optional[str]
    body_selector: Optional[str]
    image_selector: Optional[str]
    date_selector: Optional[str]
    author_selector: Optional[str]
    confidence_score: float
    sample_extraction: SampleExtraction
    warning: Optional[str] = None
    source_id: Optional[int] = None


class AnalyzeHTMLIn(BaseModel):
    html: str = Field(..., min_length=100)
    source_url: str = Field(..., max_length=500)
    source_name: str = Field(..., min_length=1, max_length=255)
    category: Optional[str] = None


class VerifyProfileOut(BaseModel):
    success: bool
    title: Optional[str] = None
    body_preview: Optional[str] = None
    message: str
    last_verified: datetime


# ─── Article ──────────────────────────────────────────────────────────────────

class ArticleOut(BaseModel):
    id: int
    source_id: int
    source: Optional[SourceBasic] = None  # Objeto fuente anidado con datos completos
    title: str
    content: Optional[str]
    excerpt: Optional[str]
    image_url: Optional[str]
    original_url: str
    category: Optional[str]
    impact_score: float
    is_breaking: bool
    status: str
    published_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Health ──────────────────────────────────────────────────────────────────

class HealthOut(BaseModel):
    status: str
    version: str = "0.1.0"
    service: str = "Byline"


# ─── Client Update (PATCH) ──────────────────────────────────────────────────

class ClientUpdate(BaseModel):
    """Schema para actualización parcial de cliente."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan: Optional[str] = Field(None, pattern=r"^(basic|pro|business)$")
    is_active: Optional[bool] = None


class ClientUpdateOut(BaseModel):
    """Respuesta tras actualizar un cliente."""
    id: int
    name: str
    plan: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Stats ────────────────────────────────────────────────────────────────────

class StatsOut(BaseModel):
    """Estadísticas del día actual."""
    articles_today: int
    breaking_today: int
    active_sources: int
    total_clients: int
    active_clients: int
    articles_discarded_today: int


# ─── Activity Log ─────────────────────────────────────────────────────────────

class LogOut(BaseModel):
    """Entrada de log de actividad."""
    id: int
    action: str
    result: str
    detail: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Article List (Admin) ───────────────────────────────────────────────────

class ArticleListItem(BaseModel):
    """Artículo para lista administrativa."""
    id: int
    source_name: str  # Nombre de la fuente
    title: str
    category: Optional[str]
    impact_score: float
    is_breaking: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
