# Monitor Externo - Script para mantener Render activo desde servicios externos
# 
# USO OPCIONAL: Si quieres un respaldo adicional al keep-alive interno,
# puedes usar servicios gratuitos como:
# - UptimeRobot (https://uptimerobot.com)
# - Cron-job.org (https://cron-job.org)
# - Kinsta Uptime Monitor (https://kinsta.com)
#
# Configura el monitor para que haga GET a:
# https://byline-dgpt.onrender.com/ping
# 
# Intervalo recomendado: cada 10-12 minutos
#

import requests
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# URL de tu API en Render
API_URL = "https://byline-dgpt.onrender.com"

def ping_api():
    """Hace ping a la API para mantenerla activa."""
    try:
        response = requests.get(f"{API_URL}/ping", timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Ping exitoso - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        else:
            logger.warning(f"⚠️ Código de respuesta: {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("❌ Timeout - La API no respondió a tiempo")
        return False
    except requests.exceptions.ConnectionError:
        logger.error("❌ Error de conexión - La API puede estar caída")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    logger.info("Iniciando ping a Render API...")
    success = ping_api()
    
    if success:
        print("✅ Ping exitoso")
    else:
        print("❌ Ping fallido")
