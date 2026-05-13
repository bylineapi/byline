# keep_alive.py - Sistema para mantener Render activo mediante pings periódicos

import logging
import asyncio
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Intervalo en minutos entre pings (Render se duerme después de 15 min de inactividad)
PING_INTERVAL_MINUTES = 12

# URL de la API (se configura al iniciar)
API_URL = None


def set_api_url(url: str):
    """Configura la URL de la API para los pings."""
    global API_URL
    API_URL = url.rstrip("/")


async def ping_api():
    """
    Hace una solicitud HTTP al endpoint /health de la propia API
    para mantener Render activo.
    """
    if not API_URL:
        logger.warning("API_URL no configurada, skipping ping")
        return
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_URL}/health")
            
            if response.status_code == 200:
                logger.info(
                    "✅ Ping exitoso a %s/health - %s",
                    API_URL,
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                )
            else:
                logger.warning(
                    "⚠️ Ping respondió con código %d",
                    response.status_code
                )
    except Exception as e:
        logger.error("❌ Error haciendo ping: %s", e)


async def keep_alive_job():
    """
    Job que se ejecuta periódicamente para mantener Render activo.
    Hace ping al endpoint /health de la API.
    """
    logger.info("Iniciando keep_alive_job (cada %d minutos)", PING_INTERVAL_MINUTES)
    
    while True:
        try:
            await ping_api()
            
            # Esperar el intervalo especificado
            await asyncio.sleep(PING_INTERVAL_MINUTES * 60)
            
        except Exception as e:
            logger.error("Error en keep_alive_job: %s", e)
            # Esperar 1 minuto antes de reintentar en caso de error
            await asyncio.sleep(60)


def start_keep_alive():
    """
    Inicia el keep_alive_job en el event loop actual.
    Debe llamarse después de que la aplicación haya iniciado.
    """
    if not API_URL:
        logger.warning("API_URL no configurada, keep-alive desactivado")
        return None
    
    loop = asyncio.get_event_loop()
    task = loop.create_task(keep_alive_job())
    
    logger.info("Keep-alive iniciado: ping cada %d minutos a %s", PING_INTERVAL_MINUTES, API_URL)
    
    return task


def stop_keep_alive(task):
    """Detiene el keep-alive."""
    if task:
        task.cancel()
        logger.info("Keep-alive detenido")
