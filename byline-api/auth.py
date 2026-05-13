# auth.py - Autenticación por API Key, planes de suscripción y dependencias

import os
import bcrypt
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dotenv import load_dotenv

from database import get_db
from models import Client, PlanEnum

load_dotenv()

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change-me")


# ─── Planes de suscripción ───────────────────────────────────────────────────

SUSCRIPTION_PLANS = {
    "basic": {
        "max_sources": 5,
        "posts_per_category_hour": 2,
        "breaking_news": False,
        "full_content": False,
        "ai_summary": False,
    },
    "pro": {
        "max_sources": 20,
        "posts_per_category_hour": 5,
        "breaking_news": True,
        "full_content": True,
        "ai_summary": True,
    },
    "business": {
        "max_sources": 999,
        "posts_per_category_hour": 999,
        "breaking_news": True,
        "full_content": True,
        "ai_summary": True,
    },
}


# ─── Utilidades de hashing ────────────────────────────────────────────────────

def hash_api_key(api_key: str) -> str:
    """Hashea una API key con bcrypt y retorna el hash."""
    return bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_api_key(api_key: str, hashed: str) -> bool:
    """Verifica una API key contra un hash guardado."""
    return bcrypt.checkpw(api_key.encode("utf-8"), hashed.encode("utf-8"))


# ─── Dependencia de autenticación ─────────────────────────────────────────────

async def get_current_client(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Client:
    """Valida el header X-API-KEY y retorna el cliente autenticado con su plan."""
    result = await db.execute(select(Client).where(Client.is_active.is_(True)))
    clients = result.scalars().all()

    for client in clients:
        if verify_api_key(x_api_key, client.api_key):
            return client

    raise HTTPException(status_code=401, detail="API Key inválida o cliente inactivo")


# ─── Dependencia de admin ─────────────────────────────────────────────────────

def verify_admin_secret(x_admin_secret: str = Header(...)):
    """Verifica el ADMIN_SECRET para operaciones administrativas."""
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin secret inválido")
    return True
