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
from category_detector import detectar_categoria_texto
from urllib.parse import urlparse, urljoin

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


def _discover_articles_from_url(url: str) -> list[str]:
    """
    Analiza una página principal (Home) y extrae enlaces que parecen ser noticias.
    """
    logger.info("🔍 Descubriendo artículos en: %s", url)
    enlaces_noticias = []
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BylineDiscovery/1.0)"
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = urlparse(url).netloc

        # Patrones comunes de noticias en URLs
        patrones_noticia = [
            r'/\d{4}/\d{2}/\d{2}/', # Fechas
            r'/noticia/', r'/articulo/', r'/p/', r'/n/',
            r'-noticia-', r'\.html$', r'-n\d+\.html$'
        ]

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(url, href)
            parsed_href = urlparse(full_url)
            
            # Solo enlaces del mismo dominio
            if parsed_href.netloc != domain:
                continue
            
            # Ignorar la home misma y secciones cortas
            path = parsed_href.path
            if len(path) < 10 or path == "/":
                continue

            # Heurística 1: Patrones de URL
            es_noticia = any(re.search(p, path) for p in patrones_noticia)
            
            # Heurística 2: Longitud del texto del enlace (titulares suelen ser largos)
            texto_enlace = a.get_text(strip=True)
            if not es_noticia and len(texto_enlace) > 40:
                es_noticia = True
            
            if es_noticia and full_url not in enlaces_noticias:
                enlaces_noticias.append(full_url)

        logger.info("✅ Se descubrieron %d posibles noticias en %s", len(enlaces_noticias), url)
    except Exception as e:
        logger.error("Error descubriendo artículos en %s: %s", url, e)
    
    return enlaces_noticias[:10] # Limitar descubrimiento a 10 para no saturar


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


def _parsear_fecha_rss(entry_dict) -> Optional[datetime]:
    """Intenta parsear la fecha de publicación desde un diccionario de entrada."""
    # Nota: Si viene de descubrimiento directo, no tendremos fecha en el 'entry'
    # newspaper3k se encargará de extraerla del HTML si es posible.
    return None


async def fetch_rss(source: Source, source_profile: Optional[dict] = None, force_date: Optional[datetime] = None, limit: Optional[int] = None) -> tuple[list[dict], Optional[dict]]:
    """
    Lee el RSS o la URL de una fuente, extrae artículos nuevos y retorna una lista
    de diccionarios con los datos crudos listos para puntuar.
    """
    logger.info("📰 Scraping fuente: %s (%s)", source.name, source.rss_url or source.url)
    articulos_crudos = []
    nuevo_perfil_aprendido = None
    loop = asyncio.get_running_loop()

    # --- OBTENER ENTRADAS (Desde RSS o desde URL Directa) ---
    entradas_a_procesar = []

    try:
        if source.rss_url:
            # Método tradicional: RSS
            logger.info("Descargando RSS de: %s", source.rss_url)
            feed = await loop.run_in_executor(
                None,
                lambda: feedparser.parse(source.rss_url),
            )

            if feed.bozo:
                logger.warning("⚠️ Warning parseando RSS de %s: %s", source.name, feed.bozo_exception)
            
            if feed.entries:
                logger.info("✅ RSS parseado: %d entradas encontradas", len(feed.entries))
                for entry in feed.entries:
                    # Intentar obtener fecha del objeto feedparser antes de convertir a dict
                    fecha = None
                    for campo in ("published_parsed", "updated_parsed"):
                        ts = getattr(entry, campo, None)
                        if ts:
                            try:
                                from time import mktime
                                fecha = datetime.fromtimestamp(mktime(ts))
                                break
                            except Exception: continue

                    entradas_a_procesar.append({
                        "link": entry.get("link", "").strip(),
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", "")),
                        "published_at": fecha
                    })
            else:
                logger.warning("❌ No se encontraron entradas en RSS de %s", source.name)
        
        # Si no hubo RSS o falló, pero tenemos una URL directa
        if not entradas_a_procesar and source.url:
            logger.info("🌐 RSS no disponible, intentando descubrimiento directo en: %s", source.url)
            urls_descubiertas = await loop.run_in_executor(
                None, _discover_articles_from_url, source.url
            )
            for link in urls_descubiertas:
                entradas_a_procesar.append({
                    "link": link,
                    "title": None,
                    "summary": None,
                    "published_at": None
                })

        if not entradas_a_procesar:
            logger.warning("❌ No se pudo obtener ninguna noticia para %s", source.name)
            return articulos_crudos, None

        # Determinar si usamos el profiler
        usar_profiler = (
            source_profile is not None
            and source_profile.get("confidence_score", 0) >= MIN_CONFIDENCE_FOR_PROFILER
            and source_profile.get("body_selector")
        )

        logger.info("✅ Procesando %d entradas (límite: %d)", 
                   len(entradas_a_procesar), limit or MAX_ARTICLES_PER_SOURCE)
        
        # --- AUTO-PROFILING: Si no tenemos perfil o es de baja confianza, intentar aprender ---
        if not usar_profiler:
            logger.info("🤖 Auto-Profiling: Intentando aprender selectores para %s...", source.name)
            url_muestra = entradas_a_procesar[0]["link"]
            
            if url_muestra:
                try:
                    resp_muestra = await loop.run_in_executor(
                        None, 
                        lambda: requests.get(url_muestra, timeout=HTTP_TIMEOUT, headers={
                            "User-Agent": "Mozilla/5.0 (compatible; BylineAutoBot/1.0)"
                        })
                    )
                    resp_muestra.raise_for_status()
                    
                    analisis = _profiler.analyze(resp_muestra.text, url_muestra)
                    if analisis.get("confidence_score", 0) >= 0.6:
                        logger.info("✅ Selectores aprendidos para %s (confidence: %.2f)", source.name, analisis["confidence_score"])
                        nuevo_perfil_aprendido = {
                            "title_selector": analisis.get("title_selector"),
                            "body_selector": analisis.get("body_selector"),
                            "image_selector": analisis.get("image_selector"),
                            "date_selector": analisis.get("date_selector"),
                            "author_selector": analisis.get("author_selector"),
                            "confidence_score": analisis["confidence_score"],
                        }
                        # Usar el perfil recién aprendido para esta sesión
                        source_profile = nuevo_perfil_aprendido
                        usar_profiler = True
                except Exception as e:
                    logger.warning("❌ Falló el auto-profiling para %s: %s", source.name, e)

        # Limitar a los artículos solicitados
        max_to_fetch = limit or MAX_ARTICLES_PER_SOURCE
        final_list = entradas_a_procesar[:max_to_fetch]

        for idx, entry in enumerate(final_list):
            original_url = entry.get("link", "").strip()
            if not original_url:
                continue
            
            logger.info("📄 Procesando artículo %d/%d: %s", idx + 1, len(final_list), original_url[:80])

            # Extraer datos según el método disponible
            if usar_profiler:
                datos_profiler = await loop.run_in_executor(
                    None, lambda: _extraer_con_profiler(original_url, source_profile)
                )
                datos_newspaper = datos_profiler if datos_profiler else await loop.run_in_executor(
                    None, _extraer_con_newspaper, original_url
                )
            else:
                datos_newspaper = await loop.run_in_executor(
                    None, _extraer_con_newspaper, original_url
                )

            title = datos_newspaper["title"] or _limpiar_html(entry.get("title", ""))
            content = datos_newspaper["content"] or _limpiar_html(entry.get("summary", ""))
            image_url = datos_newspaper["image_url"]
            published_at = datos_newspaper["published_at"] or entry.get("published_at")

            # --- DETECCIÓN DE CATEGORÍA POR ARTÍCULO ---
            category_detectada = detectar_categoria_texto(title, content)
            category = category_detectada or source.category

            if not image_url:
                image_url = await loop.run_in_executor(None, _extraer_og_image, original_url)

            if not content:
                content = _limpiar_html(entry.get("summary", ""))

            excerpt = _extraer_excerpt(content)
            
            if not title:
                continue

            articulo = {
                "source_id": source.id,
                "title": title,
                "content": content,
                "excerpt": excerpt,
                "image_url": image_url,
                "original_url": original_url,
                "category": category,
                "impact_score": 0.0,
                "is_breaking": False,
                "status": "pending",
                "published_at": force_date or published_at or datetime.utcnow(),
                "created_at": force_date or datetime.utcnow(),
            }
            articulos_crudos.append(articulo)
            
            if idx < len(final_list) - 1:
                await asyncio.sleep(ARTICLE_DELAY_SECONDS)

        logger.info("✅ Fuente %s: %d artículos extraídos", source.name, len(articulos_crudos))

    except Exception as e:
        logger.error("Error procesando fuente %s: %s", source.name, e)

    return articulos_crudos, nuevo_perfil_aprendido
