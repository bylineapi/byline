import os
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import NullPool

# Leer URL de las variables de entorno
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Limpiar la URL: asyncpg necesita postgresql+asyncpg://
# Neon a veces retorna postgresql:// — corregir automáticamente
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

# Remover ?sslmode=require de la URL porque asyncpg
# no lo acepta como parámetro de URL — se pasa via ssl=True
if "?sslmode=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("?sslmode=require", "")

# Remover channel_binding=require que Neon añade a la URL
if "channel_binding=require" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("channel_binding=require", "")
    # Limpiar & o ? que queden orphan
    DATABASE_URL = DATABASE_URL.replace("&&", "&").replace("?&", "?").strip("?&")

# Configurar SSL para Neon
ssl_context = ssl.create_default_context()

# Crear engine con SSL correcto para asyncpg + Neon
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    connect_args={"ssl": ssl_context}
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    from models import (
        Client, Source, Article, ClientArticle, 
        SourceProfile, ActivityLog, AIKey
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Auto-migración para el nuevo campo premium_image_url
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE articles ADD COLUMN premium_image_url VARCHAR(500)"))
            print("📅 Auto-migración: Columna 'premium_image_url' agregada con éxito")
        except Exception:
            # Si ya existe o falla por otra razón, no interrumpe el arranque
            pass


get_session_maker = AsyncSessionLocal