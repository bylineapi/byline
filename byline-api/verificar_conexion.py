"""
Script para verificar la conexión a Neon antes del deploy.
Ejecutar con: python verificar_conexion.py
"""
import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.pool import NullPool

load_dotenv()


async def verificar():
    url = os.getenv("DATABASE_URL")

    if not url:
        print("❌ ERROR: DATABASE_URL no está en el .env")
        return

    print(f"🔄 Conectando a Neon...")

    try:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif not url.startswith("postgresql+asyncpg://"):
            url = f"postgresql+asyncpg://{url.split('://', 1)[1]}"

        url = url.replace("?sslmode=require&channel_binding=require", "")
        url = url.replace("?sslmode=require", "")

        engine = create_async_engine(
            url,
            poolclass=NullPool,
            connect_args={"ssl": True}
        )
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Conexión exitosa")
            print(f"📦 PostgreSQL: {version}")

        await engine.dispose()

        print("✅ Conexión verificada")
        print("Ahora creando tablas...")

        from sqlalchemy.orm import DeclarativeBase

        class Base(DeclarativeBase):
            pass

        from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum, Float
        from datetime import datetime
        import enum

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

        class Client(Base):
            __tablename__ = "clients"
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(255), nullable=False)
            api_key = Column(String(255), nullable=False, unique=True)
            plan = Column(SAEnum(PlanEnum), default=PlanEnum.basic, nullable=False)
            is_active = Column(Boolean, default=True, nullable=False)
            created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

        class Source(Base):
            __tablename__ = "sources"
            id = Column(Integer, primary_key=True, autoincrement=True)
            name = Column(String(255), nullable=False)
            url = Column(String(500), nullable=True)
            rss_url = Column(String(500), nullable=False, unique=True)
            category = Column(String(100), nullable=True)
            favicon_url = Column(String(500), nullable=True)
            is_active = Column(Boolean, default=True, nullable=False)
            created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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

        class ClientArticle(Base):
            __tablename__ = "client_articles"
            id = Column(Integer, primary_key=True, autoincrement=True)
            client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
            article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
            wp_post_id = Column(Integer, nullable=True)
            published_at = Column(DateTime, nullable=True)

        class ActivityLog(Base):
            __tablename__ = "activity_logs"
            id = Column(Integer, primary_key=True, autoincrement=True)
            action = Column(String(100), nullable=False)
            result = Column(String(20), nullable=False)
            detail = Column(Text, nullable=True)
            created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

        engine2 = create_async_engine(
            url,
            poolclass=NullPool,
            connect_args={"ssl": True}
        )
        async with engine2.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tablas creadas/verificadas en Neon")
        await engine2.dispose()

    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        import traceback
        traceback.print_exc()
        print("Verifica que DATABASE_URL está correcto en .env")


asyncio.run(verificar())