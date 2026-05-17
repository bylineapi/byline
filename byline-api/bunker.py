# bunker.py - Módulo de evasión de bloqueos y seguridad perimetral (Bunker) para Byline API
# Implementa rotación de agentes, personificaciones de navegador reales y fallbacks de proxy de Google a costo $0.

import logging
import random
import time
from typing import Optional
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)

# Configuración de timeout predeterminada
HTTP_TIMEOUT = 30

# Personas de navegación realistas para engañar sistemas anti-bot (Cloudflare, Akamai, etc.)
BROWSER_PERSONAS = [
    # Chrome en Windows 11
    {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
    },
    # Firefox en Windows 11
    {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
    },
    # Safari en macOS Sonoma
    {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
    },
    # Chrome en Android (Pixel 8)
    {
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
        }
    }
]

def obtener_html_bunker(url: str) -> Optional[str]:
    """
    Descarga el contenido HTML de una URL utilizando técnicas avanzadas de evasión (Bunker):
    1. Rotación aleatoria de perfiles de navegación realistas (headers y User-Agents completos).
    2. Simulación de Referer del mismo sitio para ocultar el origen de la API.
    3. Persistencia de Cookies mediante sesión HTTP para sortear muros ligeros.
    4. Demoras aleatorias (jitter) para romper patrones de solicitudes robotizadas.
    5. Fallback a Google Translate Proxy (hace que Google actúe como proxy sin costo y 100% indetectable).
    6. Fallback a Google Web Cache si todo lo anterior falla.
    """
    persona = random.choice(BROWSER_PERSONAS)
    headers = persona["headers"].copy()

    # Añadir referer del mismo dominio
    try:
        parsed_url = urlparse(url)
        headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"
    except Exception:
        pass

    session = requests.Session()

    # Sleep aleatorio (jitter) entre 1 y 3 segundos para despistar rastreadores de velocidad
    time.sleep(random.uniform(1.0, 3.0))

    try:
        logger.info("🛡️ [Bunker] Descargando URL de forma segura directa: %s", url)
        resp = session.get(url, timeout=HTTP_TIMEOUT, headers=headers, allow_redirects=True)
        
        # Detectar patrones de bloqueo comunes (status 403, 429 o contenido de Cloudflare / Akamai)
        html_detect = resp.text.lower()
        es_bloqueado = resp.status_code in (403, 429) or "cloudflare" in html_detect or "challenge-platform" in html_detect or "captcha" in html_detect
        
        if es_bloqueado:
            raise requests.HTTPError(f"Evasión requerida. Servidor respondió con estado {resp.status_code} o pantalla de bot.")

        resp.raise_for_status()
        return resp.text

    except Exception as e:
        logger.warning("⚠️ [Bunker] Bloqueo o error en descarga directa de %s: %s. Activando escudos bunker...", url, e)
        
        # --- FALLBACK A: Google Translate Proxy ---
        try:
            # Al usar Google Translate, la petición la hacen los IPs de Google, saltando cualquier Cloudflare/IP Ban.
            google_proxy_url = f"https://translate.google.com/translate?sl=auto&tl=es&u={url}"
            logger.info("🛡️ [Bunker Escudo A] Usando Google Translate Proxy para saltar bloqueo: %s", google_proxy_url)
            
            google_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "es-ES,es;q=0.9",
            }
            
            resp = session.get(google_proxy_url, timeout=HTTP_TIMEOUT, headers=google_headers)
            resp.raise_for_status()
            return resp.text
            
        except Exception as e_a:
            logger.warning("❌ [Bunker Escudo A] Fallback de Google Translate fallido: %s. Probando Escudo B...", e_a)
            
            # --- FALLBACK B: Google Web Cache ---
            try:
                google_cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
                logger.info("🛡️ [Bunker Escudo B] Consultando memoria caché de Google: %s", google_cache_url)
                
                resp = session.get(google_cache_url, timeout=HTTP_TIMEOUT, headers=headers)
                resp.raise_for_status()
                return resp.text
            except Exception as e_b:
                logger.error("❌ [Bunker] Todos los escudos anti-bloqueo fallaron para %s: %s", url, e_b)
                
    return None
