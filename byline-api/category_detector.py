# category_detector.py - Detección automática de categorías para fuentes RSS

import logging
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)

# Mapeo de palabras clave a categorías predefinidas
CATEGORY_KEYWORDS = {
    "tecnologia": [
        "tecnologia", "technology", "tech", "digital", "software", "hardware",
        "internet", "computacion", "informatica", "ciencia", "science",
        "innovacion", "startup", "inteligencia artificial", "ai", "robotica",
        "cybersecurity", "ciberseguridad", "datos", "data"
    ],
    "politica": [
        "politica", "politics", "gobierno", "government", "congreso",
        "senado", "elecciones", "elections", "presidente", "president",
        "democracia", "democracy", "parlamento", "estado", "nation"
    ],
    "economia": [
        "economia", "economy", "finanzas", "finance", "mercados", "markets",
        "bolsa", "stock", "dinero", "money", "negocios", "business",
        "comercio", "trade", "inversion", "investment", "banca", "banking",
        "cryptomoneda", "crypto", "bitcoin"
    ],
    "deportes": [
        "deportes", "sports", "futbol", "soccer", "basketball", "tennis",
        "olimpicos", "olympics", "liga", "league", "mundial", "world cup",
        "atletismo", "ciclismo", "formula 1", "baseball", "beisbol", "nba",
        "campeonato", "partido", "match", "equipo", "team", "entrenador", "coach"
    ],
    "cultura": [
        "cultura", "culture", "arte", "art", "musica", "music", "cine",
        "cinema", "peliculas", "movies", "teatro", "theater", "literatura",
        "literature", "entretenimiento", "entertainment", "televisión",
        "television", "series", "libros", "books", "concierto", "festival",
        "estreno", "celebridad", "celebrity", "famosos", "espectaculos"
    ],
    "ciencia": [
        "ciencia", "science", "investigacion", "research", "descubrimiento",
        "discovery", "espacio", "space", "nasa", "medicina", "medicine",
        "biologia", "biology", "quimica", "chemistry", "fisica", "physics",
        "estudio cientifico", "vacuna", "genetica", "astronomia"
    ],
    "salud": [
        "salud", "health", "bienestar", "wellness", "fitness", "nutricion",
        "dieta", "enfermedad", "disease", "sintomas", "tratamiento", "hospital",
        "medico", "doctor", "psicologia", "mental health", "virus", "bacteria",
        "prevencion", "curiosidades medicas"
    ],
    "internacional": [
        "internacional", "international", "mundo", "world", "global",
        "exterior", "onu", "un", "europa", "europe", "asia", "africa",
        "latinoamerica", "latin america", "diplomacia", "diplomacy", "guerra",
        "war", "conflicto", "paz", "frontera"
    ],
    "sociedad": [
        "sociedad", "society", "social", "comunidad", "community",
        "educacion", "education", "familia", "family", "mujer", "women",
        "genero", "gender", "diversidad", "diversity", "religion",
        "iglesia", "church", "derechos humanos", "human rights", "protesta"
    ],
    "seguridad": [
        "seguridad", "security", "crimen", "crime", "policia", "police",
        "violencia", "violence", "terrorismo", "terrorism", "justicia",
        "justice", "ley", "law", "carcel", "prison", "accidente", "robo",
        "asalto", "investigacion policial", "fiscalia"
    ],
    "opinion": [
        "opinion", "editorial", "columna", "column", "analisis", "analysis",
        "comentario", "commentary", "blog", "tribuna", "plataforma", "punto de vista"
    ],
}

# Palabras clave del título del feed que pueden indicar categoría
FEED_TITLE_KEYWORDS = {
    "tecnologia": ["tech", "tecnologia", "digital", "ciencia"],
    "deportes": ["deportes", "sports", "sport"],
    "economia": ["economia", "economy", "finanzas", "finance", "negocios"],
    "politica": ["politica", "politics", "gobierno"],
    "cultura": ["cultura", "culture", "arte", "entretenimiento"],
    "ciencia": ["ciencia", "science", "investigacion"],
    "internacional": ["world", "mundo", "international", "global"],
}


def detectar_categoria_desde_feed(rss_url: str) -> Optional[str]:
    """
    Descarga y analiza un feed RSS para detectar automáticamente su categoría.
    
    Args:
        rss_url: URL del feed RSS
        
    Returns:
        Categoría detectada o None si no se pudo determinar
    """
    try:
        # Parsear el feed
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            logger.warning("Feed sin entradas: %s", rss_url)
            return None
        
        # 1. Intentar detectar desde el título/descripción del feed
        feed_title = (feed.feed.get("title", "") + " " + feed.feed.get("description", "")).lower()
        
        for category, keywords in FEED_TITLE_KEYWORDS.items():
            if any(kw in feed_title for kw in keywords):
                logger.info("Categoría detectada desde título del feed: %s -> %s", rss_url, category)
                return category
        
        # 2. Analizar categorías/tags del feed
        feed_tags = feed.feed.get("tags", [])
        for tag in feed_tags:
            tag_term = tag.get("term", "").lower()
            for category, keywords in CATEGORY_KEYWORDS.items():
                if any(kw in tag_term for kw in keywords):
                    logger.info("Categoría detectada desde tags del feed: %s -> %s", rss_url, category)
                    return category
        
        # 3. Analizar las últimas 5 entradas
        categorias_encontradas = {}
        entradas_a_analizar = feed.entries[:5]
        
        for entry in entradas_a_analizar:
            # Analizar título
            title = entry.get("title", "").lower()
            
            # Analizar categorías de la entrada
            entry_categories = []
            if hasattr(entry, "tags"):
                for tag in entry.tags:
                    entry_categories.append(tag.get("term", "").lower())
            
            # Analizar summary/descripción
            summary = entry.get("summary", "").lower()
            
            # Combinar todo el texto
            texto_completo = f"{title} {' '.join(entry_categories)} {summary}"
            
            # Buscar coincidencias con keywords
            for category, keywords in CATEGORY_KEYWORDS.items():
                coincidencias = sum(1 for kw in keywords if kw in texto_completo)
                if coincidencias > 0:
                    categorias_encontradas[category] = categorias_encontradas.get(category, 0) + coincidencias
        
        # Retornar la categoría con más coincidencias
        if categorias_encontradas:
            categoria_detectada = max(categorias_encontradas, key=categorias_encontradas.get)
            logger.info(
                "Categoría detectada desde contenido: %s -> %s (score: %d)",
                rss_url, categoria_detectada, categorias_encontradas[categoria_detectada]
            )
            return categoria_detectada
        
        logger.info("No se pudo detectar categoría para: %s", rss_url)
        return None
        
    except Exception as e:
        logger.error("Error detectando categoría para %s: %s", rss_url, e)
        return None


def detectar_categoria_texto(titulo: str, contenido: str) -> Optional[str]:
    """
    Detecta la categoría de un artículo basándose en su título y contenido.
    
    Args:
        titulo: Título del artículo
        contenido: Contenido del artículo
        
    Returns:
        Categoría detectada o None si no se pudo determinar
    """
    if not titulo and not contenido:
        return None
        
    texto_completo = f"{titulo or ''} {contenido or ''}".lower()
    
    categorias_encontradas = {}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        # Dar más peso a coincidencias en el título
        score_titulo = sum(3 for kw in keywords if titulo and kw in titulo.lower())
        # Menos peso a coincidencias en el cuerpo
        score_cuerpo = sum(1 for kw in keywords if contenido and kw in contenido.lower())
        
        total_score = score_titulo + score_cuerpo
        if total_score > 0:
            categorias_encontradas[category] = total_score
            
    if not categorias_encontradas:
        return None
        
    # Retornar la categoría con mayor puntuación
    return max(categorias_encontradas, key=categorias_encontradas.get)


def obtener_nombre_desde_feed(rss_url: str) -> Optional[str]:
    """
    Obtiene el nombre de la fuente desde el feed RSS.
    
    Args:
        rss_url: URL del feed RSS
        
    Returns:
        Nombre de la fuente o None si no se pudo obtener
    """
    try:
        feed = feedparser.parse(rss_url)
        
        # Intentar obtener el título del feed
        title = feed.feed.get("title", "").strip()
        
        if title:
            return title
        
        # Si no hay título, extraer del dominio
        from urllib.parse import urlparse
        domain = urlparse(rss_url).netloc
        if domain:
            # Remover www. y tomar la parte principal
            domain = domain.replace("www.", "")
            return domain.split(".")[0].title()
        
        return None
        
    except Exception as e:
        logger.error("Error obteniendo nombre del feed %s: %s", rss_url, e)
        return None
