# ai_manager.py - Gestor del Pool de API Keys de IA, Rotación, Fallback y Procesamiento de Artículos

import json
import logging
import random
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session_maker
from models import AIKey

logger = logging.getLogger(__name__)

# Configuración del enfriamiento de llaves (en segundos)
COOLDOWN_TIME_SECONDS = 300  # 5 minutos de enfriamiento si da 429 Rate Limit
key_cooldowns: Dict[int, datetime] = {}  # key_id -> timestamp de liberación

async def get_active_keys(db: AsyncSession, provider: str) -> List[AIKey]:
    """Obtiene todas las llaves de IA activas para un proveedor específico."""
    query = select(AIKey).where(
        AIKey.provider == provider,
        AIKey.is_active == True
    ).order_by(AIKey.usage_count.asc())
    
    result = await db.execute(query)
    keys = result.scalars().all()
    
    # Filtrar llaves que estén en periodo de enfriamiento (cooldown)
    now = datetime.utcnow()
    available_keys = []
    for key in keys:
        if key.id in key_cooldowns:
            if now < key_cooldowns[key.id]:
                logger.debug(f"Llave {key.id} de {provider} en cooldown hasta {key_cooldowns[key.id]}")
                continue
            else:
                # El cooldown ya expiró
                del key_cooldowns[key.id]
        available_keys.append(key)
        
    return available_keys

async def mark_key_success(key_id: int):
    """Incrementa el contador de uso y actualiza el timestamp de último uso de una llave."""
    async with get_session_maker() as db:
        query = update(AIKey).where(AIKey.id == key_id).values(
            usage_count=AIKey.usage_count + 1,
            last_used=datetime.utcnow()
        )
        await db.execute(query)
        await db.commit()

async def mark_key_cooldown(key_id: int):
    """Coloca una llave en cooldown tras recibir un error de límite de velocidad (Rate Limit / 429)."""
    cooldown_until = datetime.utcnow()
    # Poner en cooldown
    key_cooldowns[key_id] = cooldown_until
    logger.warning(f"🔑 Llave {key_id} colocada en cooldown hasta {cooldown_until}")

async def call_gemini_api(api_key: str, prompt: str) -> Optional[str]:
    """Llama a la API oficial de Google Gemini 1.5 Flash."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
            except (KeyError, IndexError) as e:
                logger.error(f"Error parseando respuesta de Gemini: {e}")
                return None
        elif response.status_code == 429:
            raise httpx.HTTPStatusError("Rate Limit Exceeded", request=response.request, response=response)
        else:
            logger.error(f"Gemini API devolvió código {response.status_code}: {response.text}")
            return None

async def call_groq_api(api_key: str, prompt: str) -> Optional[str]:
    """Llama a la API de Groq Cloud usando Llama 3.1 8B."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error(f"Error parseando respuesta de Groq: {e}")
                return None
        elif response.status_code == 429:
            raise httpx.HTTPStatusError("Rate Limit Exceeded", request=response.request, response=response)
        else:
            logger.error(f"Groq API devolvió código {response.status_code}: {response.text}")
            return None

async def call_openrouter_api(api_key: str, prompt: str) -> Optional[str]:
    """Llama a la API de OpenRouter usando un modelo de Llama 3 gratuito."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://byline.admin",
        "X-Title": "Byline API",
        "Content-Type": "application/json"
    }
    body = {
        "model": "meta-llama/llama-3-8b-instruct:free",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                logger.error(f"Error parseando respuesta de OpenRouter: {e}")
                return None
        elif response.status_code == 429:
            raise httpx.HTTPStatusError("Rate Limit Exceeded", request=response.request, response=response)
        else:
            logger.error(f"OpenRouter API devolvió código {response.status_code}: {response.text}")
            return None

async def rewrite_article_content(title: str, content: str) -> Dict[str, Any]:
    """
    Toma un artículo (título y contenido) y utiliza el Pool de API Keys
    con rotación y cascada (fallback) para re-escribirlo y optimizarlo para SEO.
    """
    if not title or not content:
        return {}
        
    prompt = f"""Actúa como un redactor periodístico profesional y experto en SEO. Tu tarea es re-escribir el siguiente artículo en español de forma 100% original, atractiva y optimizada para buscadores, evitando el plagio.
Debes devolver la respuesta en formato JSON estrictamente válido, con codificación UTF-8, con la siguiente estructura:
{{
  "title": "Nuevo título optimizado y llamativo",
  "content": "Cuerpo del artículo re-escrito de forma extensa y redactado profesionalmente en español, estructurado con párrafos claros.",
  "summary": "Un extracto o resumen corto y de alto impacto (máximo 150 caracteres).",
  "keywords": "palabra_clave1, palabra_clave2, palabra_clave3"
}}

Título original: {title}
Contenido original: {content}"""

    # Intentar con diferentes proveedores en cascada
    providers = ["gemini", "groq", "openrouter"]
    
    async with get_session_maker() as db:
        for provider in providers:
            # Obtener llaves activas y ordenadas por menor uso para este proveedor
            keys = await get_active_keys(db, provider)
            if not keys:
                logger.debug(f"No hay llaves activas de {provider} disponibles en el pool.")
                continue
                
            for key in keys:
                logger.info(f"Intentando procesar artículo con {provider} (Key ID: {key.id})")
                try:
                    raw_response = None
                    if provider == "gemini":
                        raw_response = await call_gemini_api(key.api_key, prompt)
                    elif provider == "groq":
                        raw_response = await call_groq_api(key.api_key, prompt)
                    elif provider == "openrouter":
                        raw_response = await call_openrouter_api(key.api_key, prompt)
                        
                    if raw_response:
                        # Limpiar posible basura antes/después del JSON en modelos no estrictos
                        raw_response = raw_response.strip()
                        if raw_response.startswith("```json"):
                            raw_response = raw_response[7:]
                        if raw_response.endswith("```"):
                            raw_response = raw_response[:-3]
                        raw_response = raw_response.strip()
                        
                        parsed = json.loads(raw_response)
                        
                        # Validar campos mínimos
                        if "title" in parsed and "content" in parsed:
                            # Incrementar estadísticas de uso de forma segura
                            await mark_key_success(key.id)
                            logger.info(f"✅ Artículo re-escrito con éxito usando {provider} (Key ID: {key.id})")
                            return {
                                "title": parsed.get("title", title),
                                "content": parsed.get("content", content),
                                "summary": parsed.get("summary", title),
                                "keywords": parsed.get("keywords", "")
                            }
                            
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning(f"⚠️ Rate Limit (429) alcanzado para la llave {key.id} de {provider}. Colocando en cooldown...")
                        await mark_key_cooldown(key.id)
                        # Sigue con la siguiente llave del mismo proveedor o pasa al siguiente
                        continue
                    else:
                        logger.error(f"Error HTTP llamando a {provider} (Key ID: {key.id}): {e}")
                except json.JSONDecodeError as e:
                    logger.error(f"Error decodificando JSON de la respuesta de {provider}: {e}. Respuesta: {raw_response}")
                except Exception as e:
                    logger.error(f"Error inesperado procesando con llave {key.id} de {provider}: {e}")
                    
    logger.warning("❌ No se pudo procesar el artículo con ninguna de las API Keys del pool. Se devolverán los textos originales.")
    return {
        "title": title,
        "content": content,
        "summary": title[:150],
        "keywords": ""
    }


async def buscar_imagen_premium(keywords: str) -> Optional[str]:
    """
    Busca una imagen profesional libre de derechos en Pixabay basada en la primera palabra clave.
    Retorna la URL de la imagen o None si falla o no hay keywords.
    """
    if not keywords:
        return None
    
    # Extraer la primera palabra clave
    parts = [p.strip() for p in keywords.split(",") if p.strip()]
    if not parts:
        return None
    
    keyword = parts[0]
    # Pixabay Key Gratuita para Byline
    pixabay_key = "43924618-ff352932d0f0eb8b3b4f65cde"
    
    try:
        url = "https://pixabay.com/api/"
        params = {
            "key": pixabay_key,
            "q": keyword,
            "image_type": "photo",
            "orientation": "horizontal",
            "per_page": 3,
            "safesearch": "true"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                if hits:
                    logger.info(f"📸 Imagen premium encontrada en Pixabay para keyword '{keyword}': {hits[0].get('largeImageURL')}")
                    return hits[0].get("largeImageURL") or hits[0].get("webformatURL")
    except Exception as e:
        logger.warning(f"Error buscando imagen premium en Pixabay para keyword '{keyword}': {e}")
    return None
                    

