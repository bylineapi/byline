# models.py - Modelos SQLAlchemy 2.0 para el sistema de distribución de noticias

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Enum as SAEnum, Float
)
from sqlalchemy.orm import relationship
from database import Base
import enum


# ─── Enumeradores ─────────────────────────────────────────────────────────────

class PlanEnum(str, enum.Enum):
    basic = "basic"
    pro = "pro"
    business = "business"


class ArticleStatusEnum(str, enum.Enum):
    pending = "pending"
    pending_normal = "pending_normal"
    pending_breaking = "pending_breaking"
    published = "published"
    discarded = "discarded"


# ─── Tabla: clients ───────────────────────────────────────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True)
    plan = Column(SAEnum(PlanEnum), default=PlanEnum.basic, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    client_articles = relationship("ClientArticle", back_populates="client")


# ─── Tabla: sources ───────────────────────────────────────────────────────────

class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500), nullable=True)
    rss_url = Column(String(500), nullable=True, unique=True)
    category = Column(String(100), nullable=True)
    favicon_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    articles = relationship("Article", back_populates="source")
    profile = relationship("SourceProfile", back_populates="source", uselist=False)


# ─── Tabla: articles ──────────────────────────────────────────────────────────

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    excerpt = Column(String(1000), nullable=True)
    image_url = Column(String(500), nullable=True)
    original_url = Column(String(500), nullable=False, unique=True)
    category = Column(String(100), nullable=True)
    impact_score = Column(Float, default=0.0, nullable=False)
    is_breaking = Column(Boolean, default=False, nullable=False)
    status = Column(SAEnum(ArticleStatusEnum), default=ArticleStatusEnum.pending, nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("Source", back_populates="articles")
    client_articles = relationship("ClientArticle", back_populates="article")


# ─── Tabla: source_profiles (perfiles de scraping aprendidos) ───────────────────

class SourceProfile(Base):
    __tablename__ = "source_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, unique=True)
    title_selector = Column(String(255), nullable=True)
    body_selector = Column(String(255), nullable=True)
    image_selector = Column(String(255), nullable=True)
    date_selector = Column(String(255), nullable=True)
    author_selector = Column(String(255), nullable=True)
    confidence_score = Column(Float, default=0.0, nullable=False)
    last_verified = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("Source", back_populates="profile")


# ─── Tabla: client_articles (rastreo de publicaciones por cliente) ───────────

class ClientArticle(Base):
    __tablename__ = "client_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    wp_post_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)

    client = relationship("Client", back_populates="client_articles")
    article = relationship("Article", back_populates="client_articles")


# ─── Tabla: activity_logs (logs de actividad del sistema) ─────────────────────

class ActivityLog(Base):
    """
    Tabla para almacenar logs de actividad del sistema.
    Usado por el scheduler y endpoints admin para registrar eventos.
    """
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(100), nullable=False)  # Nombre de la acción/evento
    result = Column(String(20), nullable=False)    # success, error, warning
    detail = Column(Text, nullable=True)          # Detalles adicionales
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
