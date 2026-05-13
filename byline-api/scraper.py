# scraper.py - Motor de scraping RSS para obtener artículos de fuentes externas

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import feedparser
import requests
from bs4 import BeautifulSoup
from newspaper import Article as NewspaperArticle

from models import Source
from profiler import HTMLProfiler

logger = logging.getLogger(__name__)

# Timeout para requests externas
HTTP_TIMEOUT = 30

# Delay entre extracción de artículos (segundos)
# Para evitar ser bloqueado por los servidores fuente
ARTICLE_DELAY_SECONDS = 15  # 15-20 segundos entre cada artículo

# Número máximo de artículos a extraer por fuente
MAX_ARTICLES_PER_SOURCE = 4

# Confidence mínima para usar el profiler en vez de newspaper3k
MIN_CONFIDENCE_FOR_PROFILER = 0.7

# Instancia global del profiler
_profiler = HTMLProfiler()


def _extraer_con_newspaper(url: str) -> dict:
    """Extrae título, contenido, imagen y fecha usando newspaper3k (bloqueante)."""
    resultado = {
        "title": None,
        "content": None,
        "image_url": None,
        "published_at": None,
    }
    try:
        logger.debug("newspaper3k descargando: %s", url)
        article = NewspaperArticle(url, language="es")
        article.download()
        article.parse()
        resultado["title"] = article.title
        resultado["content"] = article.text
        resultado["image_url"] = article.top_image
        if article.publish_date:
            resultado["published_at"] = article.publish_date
        
        logger.debug(
            "newspaper3k extrajo - Título: '%s', Contenido: %d chars, Imagen: %s",
            article.title[:50] if article.title else 'None',
            len(article.text) if article.text else 0,
            article.top_image or 'None'
        )
    except Exception as e:
        logger.warning("newspaper3k falló para %s: %s", url, e)
    return resultado


def _extraer_con_profiler(url: str, profile: dict) -> dict:
    """
    Extrae título, contenido, imagen y fecha usando el Source Profiler.
    Retorna None si la extracción falla.
    """
    try:
        resultado = _profiler.extract(url, profile)
        if resultado.get("title") and resultado.get("body"):
            return {
                "title": resultado.get("title"),
                "content": resultado.get("body"),
                "image_url": resultado.get("image_url"),
                "published_at": _parsear_fecha_str(resultado.get("date")),
            }
    except Exception as e:
        logger.warning("Profiler falló para %s: %s", url, e)
    return None


def _parsear_fecha_str(fecha_str: Optional[str]) -> Optional[datetime]:
    """Parsea una fecha en formato string a datetime."""
    if not fecha_str:
        return None
    formatos = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(fecha_str[:19], fmt)
        except (ValueError, IndexError):
            continue
    return None


def _extraer_og_image(url: str) -> Optional[str]:
    """Fallback: extrae og:image del HTML con BeautifulSoup (bloqueante)."""
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
    except Exception as e:
        logger.debug("Fallback og:image falló para %s: %s", url, e)
    return None


def _limpiar_html(texto: str) -> str:
    """Elimina etiquetas HTML y espacios redundantes."""
    if not texto:
        return ""
    limpio = re.sub(r"<[^>]+>", " ", texto)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio


def _extraer_excerpt(contenido: str, max_caracteres: int = 500) -> str:
    """Extrae los primeros párrafos como resumen."""
    if not contenido:
        return ""
    parrafos = [p.strip() for p in contenido.split("\n") if p.strip()]
    excerpt = ""
    count = 0
    for p in parrafos:
        if count >= 3:
            break
        excerpt += p + " "
        count += 1
    excerpt = excerpt[:max_caracteres].strip()
    if len(excerpt) >= max_caracteres:
        excerpt = excerpt[:max_caracteres - 3] + "..."
    return excerpt


def _parsear_fecha_rss(entry) -> Optional[datetime]:
    """Intenta parsear la fecha de publicación desde una entrada RSS."""
    for campo in ("published_parsed", "updated_parsed"):
        time_struct = getattr(entry, campo, None)
        if time_struct:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(time_struct))
            except Exception:
                continue
    return None


async def fetch_rss(source: Source, source_profile: Optional[dict] = None, force_date: Optional[datetime] = None) -> list[dict]:
    """
    Lee el RSS de una fuente, extrae artículos nuevos y retorna una lista
    de diccionarios con los datos crudos listos para puntuar.

    Cada dict contiene:
        - source_id, title, content, excerpt, image_url, original_url,
          category, impact_score (0), is_breaking (False),
          status ('pending'), published_at, created_at

    Si source_profile está disponible y tiene confidence >= 0.7,
    usa el Source Profiler en vez de newspaper3k para extraer contenido.
    
    IMPORTANTE: Agrega delay entre artículos para evitar bloqueos del servidor fuente.
    
    Args:
        force_date: Si se proporciona, usa esta fecha para todos los artículos (solo para pruebas)
    """
    logger.info("📰 Scraping fuente: %s (%s)", source.name, source.rss_url)
    articulos_crudos = []

    # Determinar si usamos el profiler
    usar_profiler = (
        source_profile is not None
        and source_profile.get("confidence_score", 0) >= MIN_CONFIDENCE_FOR_PROFILER
        and source_profile.get("body_selector")
    )

    if usar_profiler:
        logger.info(
            "Fuente %s: usando Source Profiler (confidence: %.0f%%)",
            source.name,
            source_profile.get("confidence_score", 0) * 100,
        )

    try:
        loop = asyncio.get_running_loop()

        # Descargar y parsear RSS en un hilo separado (feedparser es síncrono)
        logger.info("Descargando RSS de: %s", source.rss_url)
        feed = await loop.run_in_executor(
            None,
            lambda: feedparser.parse(source.rss_url),
        )

        if feed.bozo:
            logger.warning("⚠️ Warning parseando RSS de %s: %s", source.name, feed.bozo_exception)
        
        if not feed.entries:
            logger.warning("❌ No se encontraron entradas en RSS de %s", source.name)
            return articulos_crudos
        
        logger.info("✅ RSS parseado: %d entradas encontradas (procesando solo las %d más recientes)", 
                   len(feed.entries), MAX_ARTICLES_PER_SOURCE)

        # Limitar a los MAX_ARTICLES_PER_SOURCE artículos más recientes
        entradas_a_procesar = feed.entries[:MAX_ARTICLES_PER_SOURCE]

        for idx, entry in enumerate(entradas_a_procesar):
            original_url = entry.get("link", "").strip()
            if not original_url:
                logger.debug("Entrada %d sin URL, saltando", idx + 1)
                continue
            
            logger.info(
                "📄 Procesando artículo %d/%d: %s",
                idx + 1,
                len(entradas_a_procesar),
                original_url[:80]
            )

            # Extraer datos según el método disponible
            if usar_profiler:
                datos_profiler = await loop.run_in_executor(
                    None, lambda: _extraer_con_profiler(original_url, source_profile)
                )
                if datos_profiler:
                    datos_newspaper = datos_profiler
                else:
                    # Profiler falló, intentar con newspaper como fallback
                    logger.warning("Profiler falló, usando newspaper como fallback")
                    datos_newspaper = await loop.run_in_executor(
                        None, _extraer_con_newspaper, original_url
                    )
            else:
                # Usar newspaper3k como método principal
                datos_newspaper = await loop.run_in_executor(
                    None, _extraer_con_newspaper, original_url
                )

            title = datos_newspaper["title"] or _limpiar_html(entry.get("title", ""))
            content = datos_newspaper["content"] or _limpiar_html(
                entry.get("summary", entry.get("description", ""))
            )
            image_url = datos_newspaper["image_url"]
            published_at = datos_newspaper["published_at"] or _parsear_fecha_rss(entry)

            # Si no hay imagen, intentar og:image como fallback
            if not image_url:
                image_url = await loop.run_in_executor(
                    None, _extraer_og_image, original_url
                )

            # Si no hay contenido, usar el summary del RSS como fallback
            if not content:
                content = _limpiar_html(
                    entry.get("summary", entry.get("description", ""))
                )

            excerpt = _extraer_excerpt(content)
            
            # Verificar que al menos tengamos título
            if not title:
                logger.warning("Artículo sin título, saltando: %s", original_url)
                continue

            articulo = {
                "source_id": source.id,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "image_url": image_url,
                "original_url": original_url,
                "category": source.category,
                "impact_score": 0.0,
                "is_breaking": False,
                "status": "pending",
                "published_at": force_date or published_at or datetime.utcnow(),
                "created_at": force_date or datetime.utcnow(),
            }
            articulos_crudos.append(articulo)
            
            logger.info(
                "✅ Artículo %d/%d extraído: %s",
                idx + 1,
                len(entradas_a_procesar),
                title[:60]
            )
            
            # Delay entre artículos para evitar ser bloqueado
            if idx < len(entradas_a_procesar) - 1:  # No delay en el último artículo
                logger.info("⏳ Esperando %d segundos antes del siguiente artículo...", ARTICLE_DELAY_SECONDS)
                await asyncio.sleep(ARTICLE_DELAY_SECONDS)

        logger.info(
            "✅ Fuente %s: %d artículos extraídos de %d entradas",
            source.name, len(articulos_crudos), len(feed.entries),
        )

    except Exception as e:
        logger.error("Error procesando fuente %s: %s", source.name, e)

    return articulos_crudos
