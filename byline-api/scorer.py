# scorer.py - Sistema de puntuación de impacto para artículos

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from keywords import URGENT_KEYWORDS

logger = logging.getLogger(__name__)


class ImpactScorer:
    """
    Calcula la puntuación de impacto (0-100) de un artículo basado en:
      - Componente 1: Palabras clave urgentes (40%)
      - Componente 2: Trending multi-fuente (40%)
      - Componente 3: Frescura (20%)
    """

    # Palabras de menos de 4 caracteres se ignoran para similitud
    _MIN_WORD_LENGTH = 4

    def score(
        self,
        article: dict,
        all_recent_articles: list[dict],
    ) -> float:
        """
        Calcula y retorna el score final (0-100).

        Args:
            article: Diccionario con al menos 'title', 'content', 'published_at'
            all_recent_articles: Lista de artículos de las últimas 2 horas
                                 (excluyendo el actual) para detectar trending.
        """
        score_total = 0.0

        c1 = self._componente_keywords(article)
        c2 = self._componente_trending(article, all_recent_articles)
        c3 = self._componente_frescura(article)

        score_total = c1 + c2 + c3
        logger.debug(
            "Score para '%s': keywords=%.1f, trending=%.1f, frescura=%.1f, total=%.1f",
            article.get("title", "")[:50], c1, c2, c3, score_total,
        )

        return round(min(score_total, 100.0), 1)

    # ─── Componente 1: Palabras clave urgentes (40%) ──────────────────────

    def _componente_keywords(self, article: dict) -> float:
        """
        Busca palabras clave urgentes en el título (x2) y en el contenido (x1).
        Retorna puntaje de 0 a 40.
        """
        title = (article.get("title") or "").lower()
        content = (article.get("content") or "").lower()

        # Tomar primeros 2 párrafos del contenido
        parrafos = [p.strip() for p in content.split("\n") if p.strip()]
        primeros_parrafos = " ".join(parrafos[:2])

        palabras_encontradas = 0
        total_palabras = len(URGENT_KEYWORDS)

        for kw in URGENT_KEYWORDS:
            kw_lower = kw.lower()
            # Título pesa doble
            if kw_lower in title:
                palabras_encontradas += 2
            elif kw_lower in primeros_parrafos:
                palabras_encontradas += 1

        if total_palabras == 0:
            return 0.0

        # Normalizar: (encontradas / total) * 40, máximo 40
        raw = (palabras_encontradas / total_palabras) * 40.0
        return min(raw, 40.0)

    # ─── Componente 2: Trending multi-fuente (40%) ────────────────────────

    def _componente_trending(
        self,
        article: dict,
        all_recent_articles: list[dict],
    ) -> float:
        """
        Detecta si el mismo tema está siendo cubierto por múltiples fuentes.
        Retorna 40 si 2+ fuentes distintas cubren el mismo tema, 0 si no.
        """
        title_actual = (article.get("title") or "").lower()
        source_id_actual = article.get("source_id")

        palabras_clave_actual = self._extraer_palabras_significativas(title_actual)

        if not palabras_clave_actual:
            return 0.0

        fuentes_distintas = set()

        for otro in all_recent_articles:
            # No comparar con uno mismo
            if otro.get("source_id") == source_id_actual:
                continue

            otro_titulo = (otro.get("title") or "").lower()
            palabras_otro = self._extraer_palabras_significativas(otro_titulo)

            if not palabras_otro:
                continue

            # Calcular overlap
            overlap = palabras_clave_actual & palabras_otro
            if len(overlap) >= 2:
                fuentes_distintas.add(otro.get("source_id"))

        if len(fuentes_distintas) >= 2:
            logger.info(
                "Trending detectado: '%s' cubierto por %d fuentes",
                article.get("title", "")[:50], len(fuentes_distintas),
            )
            return 40.0

        return 0.0

    def _extraer_palabras_significativas(self, texto: str) -> set:
        """Extrae palabras de más de N caracteres, sin stopwords muy básicas."""
        if not texto:
            return set()
        stopwords = {"para", "este", "esta", "con", "por", "que", "del",
                     "las", "los", "una", "uno", "sus", "fue", "entre"}
        palabras = re.findall(r"\w{4,}", texto.lower())
        return {p for p in palabras if p not in stopwords}

    # ─── Componente 3: Frescura (20%) ─────────────────────────────────────

    def _componente_frescura(self, article: dict) -> float:
        """
        Puntúa según qué tan reciente es el artículo.
          - < 30 min: 20 puntos
          - 30-60 min: 15 puntos
          - 1-3 horas: 10 puntos
          - > 3 horas: 0 puntos
        """
        published_at = article.get("published_at")
        if not published_at:
            return 0.0

        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except (ValueError, TypeError):
                return 0.0
        
        # Si published_at tiene timezone (aware), convertir a naive
        if published_at.tzinfo is not None:
            published_at = published_at.replace(tzinfo=None)

        ahora = datetime.utcnow()
        diff = ahora - published_at

        if diff < timedelta(minutes=30):
            return 20.0
        elif diff < timedelta(minutes=60):
            return 15.0
        elif diff < timedelta(hours=3):
            return 10.0
        else:
            return 0.0
