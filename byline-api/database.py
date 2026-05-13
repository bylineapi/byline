# database.py - Conexión asíncrona a PostgreSQL con SQLAlchemy 2.0 y asyncpg

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set. Please configure it in Render dashboard.")


class Base(DeclarativeBase):
    pass


_engine = None
_async_session_maker = None


def get_engine():
    """Retorna el engine asíncrono, creándolo si es necesario."""
    global _engine
    if _engine is None:
        db_url = DATABASE_URL
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url and not db_url.startswith("postgresql+asyncpg://"):
            db_url = f"postgresql+asyncpg://{db_url.split('://', 1)[1]}"
        _engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=NullPool,
            connect_args={"ssl": True}
        )
    return _engine


def get_session_maker():
    """Retorna el sessionmaker asíncrono, creándolo si es necesario."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_maker


async def get_db() -> AsyncSession:
    """Dependencia de FastAPI que entrega una sesión de base de datos."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Crea todas las tablas definidas en models.py."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
