# profiler.py - Source Profiler: aprende selectores CSS de cualquier página web

import logging
import re
import json
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
from bunker import obtener_html_bunker

logger = logging.getLogger(__name__)

# Timeout para requests externas
HTTP_TIMEOUT = 30

# Score base según el método de detección usado
SCORE_OG_META = 1.0
SCORE_CLASS_EXACTA = 0.85
SCORE_HEURISTICA = 0.65
SCORE_FALLBACK = 0.40


class HTMLProfiler:
    """
    Analiza código HTML de una página de artículo y detecta automáticamente
    los selectores CSS necesarios para extraer contenido estructurado.
    """

    # Clases conocidas para cada tipo de elemento (búsqueda por contains)
    TITLE_CLASSES = {"article", "title", "heading", "post-title", "headline", "titulo"}
    BODY_CLASSES = {
        "content", "body", "article-body", "post-content", "entry-content",
        "story-body", "nota-contenido", "article-content", "main-content"
    }
    IMAGE_CLASSES = {"featured", "portada", "principal", "hero", "cover", "main-image"}
    DATE_CLASSES = {"date", "fecha", "published", "time", "pubdate", "timestamp"}
    AUTHOR_CLASSES = {"author", "autor", "byline", "firma", "writer", "escritor"}

    def analyze(self, html: str, source_url: str) -> dict:
        """
        Analiza el HTML crudo y retorna los selectores CSS detectados.

        Args:
            html: Código HTML completo de una página de artículo
            source_url: URL origen para referencia

        Returns:
            Diccionario con selectores, score de confianza y muestra de extracción
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extraer usando los métodos especializados
        title_result = self._detect_title(soup)
        body_result = self._detect_body(soup)
        image_result = self._detect_image(soup)
        date_result = self._detect_date(soup)
        author_result = self._detect_author(soup)

        # Calcular score promedio de confianza
        scores = [
            title_result["score"],
            body_result["score"],
            image_result["score"],
            date_result["score"],
            author_result["score"],
        ]
        confidence_score = sum(scores) / len(scores)

        # Seleccionadores encontrados
        title_selector = title_result["selector"]
        body_selector = body_result["selector"]
        image_selector = image_result["selector"]
        date_selector = date_result["selector"]
        author_selector = author_result["selector"]

        # Extraer muestra usando los selectores detectados
        sample_extraction = self._extract_sample(
            soup, title_selector, body_selector, image_selector, date_selector
        )

        return {
            "title_selector": title_selector,
            "body_selector": body_selector,
            "image_selector": image_selector,
            "date_selector": date_selector,
            "author_selector": author_selector,
            "confidence_score": round(confidence_score, 2),
            "sample_extraction": sample_extraction,
        }

    # ─── Detección de Título ───────────────────────────────────────────────────

    def _detect_title(self, soup: BeautifulSoup) -> dict:
        """
        Detecta el selector de título en orden de prioridad:
        1. og:title meta
        2. h1 con clase conocida
        3. h1 con más texto
        4. title del documento
        """
        # Prioridad 1: og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return {
                "selector": "meta[property='og:title']",
                "element": og_title,
                "score": SCORE_OG_META,
            }

        # Prioridad 2: h1 con clase que contenga keywords conocidas
        for cls in self.TITLE_CLASSES:
            h1 = soup.find("h1", class_=lambda x: x and cls in x.lower())
            if h1:
                return {
                    "selector": f"h1.{cls}",
                    "element": h1,
                    "score": SCORE_CLASS_EXACTA,
                }

        # Prioridad 3: h1 con más texto
        h1s = soup.find_all("h1")
        if h1s:
            mejor_h1 = max(h1s, key=lambda h: len(h.get_text(strip=True)))
            if mejor_h1.get_text(strip=True):
                return {
                    "selector": "h1",
                    "element": mejor_h1,
                    "score": SCORE_HEURISTICA,
                }

        # Prioridad 4: title del documento
        title_tag = soup.find("title")
        if title_tag:
            return {
                "selector": "title",
                "element": title_tag,
                "score": SCORE_FALLBACK,
            }

        return {"selector": None, "element": None, "score": 0.0}

    # ─── Detección de Cuerpo ──────────────────────────────────────────────────

    def _detect_body(self, soup: BeautifulSoup) -> dict:
        """
        Detecta el selector de cuerpo en orden de prioridad:
        1. article tag directo
        2. div/section con clase conocida
        3. div con mayor densidad de texto
        4. Eliminar: nav, header, footer, aside, ads, scripts
        """
        # Prioridad 1: article tag
        article = soup.find("article")
        if article:
            return {
                "selector": "article",
                "element": article,
                "score": SCORE_CLASS_EXACTA,
            }

        # Prioridad 2: div/section con clase conocida
        for cls in self.BODY_CLASSES:
            elem = soup.find(["div", "section"], class_=lambda x: x and cls in x.lower())
            if elem:
                return {
                    "selector": f"[class*='{cls}']",
                    "element": elem,
                    "score": SCORE_CLASS_EXACTA,
                }

        # Prioridad 3: div con mayor densidad de texto
        mejor_div = self._find_best_text_density(soup)
        if mejor_div:
            clase_div = mejor_div.get("class")
            if clase_div:
                selector = ".".join([f".{c}" for c in clase_div[:2]])
            else:
                selector = mejor_div.name or "div"
            return {
                "selector": selector,
                "element": mejor_div,
                "score": SCORE_HEURISTICA,
            }

        # Fallback: body
        body = soup.find("body")
        if body:
            return {
                "selector": "body",
                "element": body,
                "score": SCORE_FALLBACK,
            }

        return {"selector": None, "element": None, "score": 0.0}

    def _find_best_text_density(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Encuentra el div con mayor ratio texto/HTML (densidad de contenido).
        Ignora elementos de navegación, publicidades y elementos pequeños.
        """
        elementos_peligros = {
            "nav", "header", "footer", "aside", "script", "style",
            "noscript", "iframe", "form", "button", "input"
        }
        clases_peligros = {
            "ad", "publicidad", "related", "social-share", "sidebar",
            "menu", "nav", "comment", "footer", "header", "nav"
        }

        mejores_divs = []
        for div in soup.find_all("div"):
            clases = [c.lower() for c in div.get("class", [])]
            if any(c in clases_peligros for c in clases):
                continue
            if div.name in elementos_peligros:
                continue

            texto = div.get_text(separator=" ", strip=True)
            html_len = len(str(div))
            if html_len < 500:
                continue

            texto_len = len(texto)
            if texto_len < 100:
                continue

            ratio = texto_len / html_len
            if ratio > 0.1:
                mejores_divs.append((div, ratio, texto_len))

        if mejores_divs:
            return max(mejores_divs, key=lambda x: (x[1], x[2]))[0]
        return None

    # ─── Detección de Imagen ─────────────────────────────────────────────────

    def _detect_image(self, soup: BeautifulSoup) -> dict:
        """
        Detecta el selector de imagen en orden de prioridad:
        1. og:image meta
        2. twitter:image meta
        3. img dentro del cuerpo con width>300 o clase conocida
        4. Schema.org JSON-LD
        """
        # Prioridad 1: og:image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return {
                "selector": "meta[property='og:image']",
                "element": og_image,
                "score": SCORE_OG_META,
            }

        # Prioridad 2: twitter:image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return {
                "selector": "meta[name='twitter:image']",
                "element": twitter_image,
                "score": SCORE_OG_META,
            }

        # Prioridad 3: img con clase conocida o width > 300
        for cls in self.IMAGE_CLASSES:
            img = soup.find("img", class_=lambda x: x and cls in " ".join(x).lower())
            if img:
                return {
                    "selector": f"img.{cls}",
                    "element": img,
                    "score": SCORE_CLASS_EXACTA,
                }

        # Buscar por width
        for img in soup.find_all("img"):
            width = img.get("width")
            if width:
                try:
                    if int(width) > 300:
                        return {
                            "selector": "img[width>300]",
                            "element": img,
                            "score": SCORE_HEURISTICA,
                        }
                except (ValueError, TypeError):
                    pass

        # Prioridad 4: Schema.org JSON-LD
        ld_json = self._extract_ld_json(soup)
        if ld_json:
            image_url = self._get_image_from_ld_json(ld_json)
            if image_url:
                return {
                    "selector": "script[type='application/ld+json']",
                    "element": None,
                    "score": SCORE_OG_META,
                }

        return {"selector": None, "element": None, "score": 0.0}

    def _extract_ld_json(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extrae el primer JSON-LD con schema.org."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    return data
                if isinstance(data, list) and data:
                    return data[0]
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _get_image_from_ld_json(self, ld_json: dict) -> Optional[str]:
        """Extrae URL de imagen desde JSON-LD."""
        if "@type" in ld_json and "ImageObject" in str(ld_json.get("@type", "")):
            return ld_json.get("url")
        image = ld_json.get("image")
        if isinstance(image, str):
            return image
        if isinstance(image, dict):
            return image.get("url")
        if isinstance(image, list) and image:
            first = image[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url")
        return None

    # ─── Detección de Fecha ────────────────────────────────────────────────────

    def _detect_date(self, soup: BeautifulSoup) -> dict:
        """
        Detecta el selector de fecha en orden de prioridad:
        1. article:published_time meta
        2. time datetime
        3. Schema.org publishedDate
        4. Elemento con clase conocida
        """
        # Prioridad 1: article:published_time
        meta_date = soup.find("meta", property="article:published_time")
        if meta_date and meta_date.get("content"):
            return {
                "selector": "meta[property='article:published_time']",
                "element": meta_date,
                "score": SCORE_OG_META,
            }

        # Prioridad 2: time tag con datetime
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            return {
                "selector": "time[datetime]",
                "element": time_elem,
                "score": SCORE_CLASS_EXACTA,
            }

        # Prioridad 3: Schema.org publishedDate
        ld_json = self._extract_ld_json(soup)
        if ld_json:
            pub_date = ld_json.get("datePublished") or ld_json.get("publishedDate")
            if pub_date:
                return {
                    "selector": "script[type='application/ld+json']",
                    "element": None,
                    "score": SCORE_OG_META,
                }

        # Prioridad 4: elementos con clase conocida
        for cls in self.DATE_CLASSES:
            elem = soup.find(class_=lambda x: x and cls in " ".join(x).lower())
            if elem:
                return {
                    "selector": f"[class*='{cls}']",
                    "element": elem,
                    "score": SCORE_HEURISTICA,
                }

        return {"selector": None, "element": None, "score": 0.0}

    # ─── Detección de Autor ─────────────────────────────────────────────────────

    def _detect_author(self, soup: BeautifulSoup) -> dict:
        """
        Detecta el selector de autor en orden de prioridad:
        1. meta author
        2. Schema.org author.name
        3. elemento con clase conocida
        """
        # Prioridad 1: meta author
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author and meta_author.get("content"):
            return {
                "selector": "meta[name='author']",
                "element": meta_author,
                "score": SCORE_OG_META,
            }

        # Prioridad 2: Schema.org author.name
        ld_json = self._extract_ld_json(soup)
        if ld_json:
            author = ld_json.get("author")
            if author:
                if isinstance(author, str):
                    return {
                        "selector": "script[type='application/ld+json']",
                        "element": None,
                        "score": SCORE_OG_META,
                    }
                if isinstance(author, dict) and author.get("name"):
                    return {
                        "selector": "script[type='application/ld+json']",
                        "element": None,
                        "score": SCORE_OG_META,
                    }

        # Prioridad 3: elementos con clase conocida
        for cls in self.AUTHOR_CLASSES:
            elem = soup.find(class_=lambda x: x and cls in " ".join(x).lower())
            if elem:
                return {
                    "selector": f"[class*='{cls}']",
                    "element": elem,
                    "score": SCORE_HEURISTICA,
                }

        return {"selector": None, "element": None, "score": 0.0}

    # ─── Extracción de Muestra ────────────────────────────────────────────────

    def _extract_sample(
        self,
        soup: BeautifulSoup,
        title_selector: Optional[str],
        body_selector: Optional[str],
        image_selector: Optional[str],
        date_selector: Optional[str],
    ) -> dict:
        """
        Usa los selectores detectados para extraer una muestra de contenido.
        Esto permite verificar visualmente si los selectores funcionan.
        """
        sample = {}

        # Extraer título
        if title_selector:
            title_elem = self._apply_selector(soup, title_selector)
            if title_elem:
                sample["title"] = title_elem.get_text(strip=True)

        # Extraer imagen
        if image_selector:
            image_elem = self._apply_selector(soup, image_selector)
            if image_elem:
                image_url = image_elem.get("content") or image_elem.get("src")
                sample["image_url"] = image_url

        # Extraer fecha
        if date_selector:
            date_elem = self._apply_selector(soup, date_selector)
            if date_elem:
                date_value = date_elem.get("content") or date_elem.get("datetime")
                if not date_value:
                    date_value = date_elem.get_text(strip=True)
                sample["date"] = date_value

        return sample

    def _apply_selector(self, soup: BeautifulSoup, selector: str) -> Optional[BeautifulSoup]:
        """Aplica un selector CSS y retorna el elemento."""
        try:
            if selector.startswith("meta["):
                return soup.select_one(selector)
            if selector.startswith("[class*="):
                return soup.select_one(selector)
            if selector == "time[datetime]":
                return soup.find("time")
            if selector == "article":
                return soup.find("article")
            if selector == "h1":
                return soup.find("h1")
            if selector == "title":
                return soup.find("title")
            if selector == "body":
                return soup.find("body")
            if selector.startswith("img"):
                return soup.find("img")
            return soup.select_one(selector)
        except Exception:
            return None

    # ─── Extracción con Perfil Guardado ───────────────────────────────────────

    def extract(self, url: str, profile: dict) -> dict:
        """
        Descarga una URL y extrae contenido usando un perfil guardado.

        Args:
            url: URL del artículo a scrapear
            profile: Diccionario con los selectores del perfil

        Returns:
            Diccionario con title, body, image_url, date, author, original_url
        """
        html = obtener_html_bunker(url)
        if not html:
            logger.warning("Bunker no pudo descargar %s", url)
            return self._empty_result(url)

        soup = BeautifulSoup(html, "html.parser")

        resultado = {
            "title": None,
            "body": None,
            "image_url": None,
            "date": None,
            "author": None,
            "original_url": url,
        }

        # Extraer título
        title_sel = profile.get("title_selector")
        if title_sel:
            elem = self._apply_selector(soup, title_sel)
            if elem:
                resultado["title"] = elem.get_text(strip=True)
                if not resultado["title"]:
                    resultado["title"] = elem.get("content")

        # Extraer cuerpo
        body_sel = profile.get("body_selector")
        if body_sel:
            elem = self._apply_selector(soup, body_sel)
            if elem:
                resultado["body"] = self._clean_body(elem)
            else:
                # Intentar con selector genérico si falla el específico
                elem = soup.find("article") or self._find_best_text_density(soup)
                if elem:
                    resultado["body"] = self._clean_body(elem)

        # Extraer imagen
        image_sel = profile.get("image_selector")
        if image_sel:
            elem = self._apply_selector(soup, image_sel)
            if elem:
                resultado["image_url"] = elem.get("content") or elem.get("src")

        # Extraer fecha
        date_sel = profile.get("date_selector")
        if date_sel:
            elem = self._apply_selector(soup, date_sel)
            if elem:
                resultado["date"] = elem.get("content") or elem.get("datetime")
                if not resultado["date"]:
                    resultado["date"] = elem.get_text(strip=True)

        # Extraer autor
        author_sel = profile.get("author_selector")
        if author_sel:
            elem = self._apply_selector(soup, author_sel)
            if elem:
                resultado["author"] = elem.get_text(strip=True)
                if not resultado["author"]:
                    resultado["author"] = elem.get("content")

        # Si la extracción falló críticamente, re-analizar
        if not resultado["title"] or not resultado["body"]:
            logger.info("Perfil falló para %s, re-analizando", url)
            reanalizado = self.analyze(html, url)
            # Actualizar selectores en profile para siguiente intento
            profile.update({
                k: reanalizado.get(k)
                for k in ["title_selector", "body_selector", "image_selector",
                          "date_selector", "author_selector"]
            })
            # Re-intentar extracción con nuevos selectores
            return self.extract(url, profile)

        return resultado

    def _clean_body(self, element: BeautifulSoup) -> str:
        """
        Limpia el contenido del cuerpo eliminando elementos no deseados.
        """
        from bs4 import Comment
        elem_copy = BeautifulSoup(str(element), "html.parser")

        # Eliminar elementos no deseados
        for tag in elem_copy.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()

        for tag in elem_copy.find_all(class_=lambda x: x and any(
            c in " ".join(x).lower()
            for c in ["ad", "publicidad", "related", "social-share", "sidebar",
                      "comment", "nav", "menu", "footer", "header"]
        )):
            tag.decompose()

        for tag in elem_copy.find_all(["script", "style", "noscript"]):
            tag.decompose()

        # Eliminar comentarios HTML
        for comment in elem_copy.find_all(string=lambda x: isinstance(x, Comment)):
            comment.extract()

        # Eliminar clases de anuncio
        for tag in elem_copy.find_all(class_=re.compile(r"ads?|promo|spot", re.I)):
            tag.decompose()

        # Obtener texto limpio
        texto = elem_copy.get_text(separator="\n", strip=True)
        # Eliminar líneas vacías repetidas
        lines = [l.strip() for l in texto.split("\n") if l.strip()]
        return "\n\n".join(lines)

    def _empty_result(self, url: str) -> dict:
        """Retorna estructura vacía con la URL original."""
        return {
            "title": None,
            "body": None,
            "image_url": None,
            "date": None,
            "author": None,
            "original_url": url,
        }
