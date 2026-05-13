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
        SourceProfile, ActivityLog
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)