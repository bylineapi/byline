#!/usr/bin/env python3
"""
Script para agregar múltiples categorías de Diario Libre con scraping HTML.
Todos comparten el mismo perfil CSS ya aprendido.
"""

import asyncio
import os
import sys
import requests
from bs4 import BeautifulSoup

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from profiler import HTMLProfiler
from database import engine, AsyncSessionLocal
from models import Source, SourceProfile

# Lista de categorías de Diario Libre
CATEGORIAS = [
    {
        "name": "Diario Libre - Nacional",
        "url": "https://www.diariolibre.com/actualidad/nacional",
        "rss": "https://www.diariolibre.com/rss/actualidad.xml",
        "category": "nacional"
    },
    {
        "name": "Diario Libre - Salud",
        "url": "https://www.diariolibre.com/actualidad/salud",
        "rss": "https://www.diariolibre.com/rss/salud.xml",
        "category": "salud"
    },
    {
        "name": "Diario Libre - Política",
        "url": "https://www.diariolibre.com/politica",
        "rss": "https://www.diariolibre.com/rss/politica.xml",
        "category": "politica"
    },
    {
        "name": "Diario Libre - Economía",
        "url": "https://www.diariolibre.com/economia",
        "rss": "https://www.diariolibre.com/rss/economia.xml",
        "category": "economia"
    },
    {
        "name": "Diario Libre - Deportes",
        "url": "https://www.diariolibre.com/deportes",
        "rss": "https://www.diariolibre.com/rss/deportes.xml",
        "category": "deportes"
    },
]

async def main():
    print("🔍 Analizando HTML de Diario Libre para aprender selectores...")
    
    # 1. Analizar primer artículo para aprender selectores
    profiler = HTMLProfiler()
    analisis = None
    
    # Usar la primera URL para aprender los selectores
    primera_categoria = CATEGORIAS[0]
    
    try:
        response = requests.get(primera_categoria["url"], timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BylineBot/1.0)"
        })
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Buscar primer enlace a artículo
        article_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/actualidad/" in href or "/politica/" in href or "/economia/" in href:
                if href.startswith("http"):
                    article_link = href
                    break
        
        if article_link:
            print(f"📄 Analizando artículo: {article_link}")
            article_response = requests.get(article_link, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 (compatible; BylineBot/1.0)"
            })
            article_response.raise_for_status()
            analisis = profiler.analyze(article_response.text, article_link)
            
            print(f"\n📊 Selectores aprendidos:")
            print(f"   Title: {analisis['title_selector']}")
            print(f"   Body: {analisis['body_selector']}")
            print(f"   Image: {analisis['image_selector']}")
            print(f"   Date: {analisis['date_selector']}")
            print(f"   Author: {analisis['author_selector']}")
            print(f"   Confidence: {analisis['confidence_score']:.0%}\n")
        else:
            print("⚠️ No se pudo encontrar artículo para análisis")
            
    except Exception as e:
        print(f"❌ Error en análisis: {e}")
        return
    
    # 2. Agregar todas las categorías
    print(f"💾 Agregando {len(CATEGORIAS)} categorías...")
    
    async with AsyncSessionLocal() as db:
        for cat in CATEGORIAS:
            try:
                from sqlalchemy import select
                
                # Verificar si ya existe
                result = await db.execute(
                    select(Source).where(Source.rss_url == cat["rss"])
                )
                existente = result.scalar_one_or_none()
                
                if existente:
                    print(f"⚠️  {cat['name']} ya existe (ID: {existente.id})")
                    continue
                
                # Crear fuente
                nueva_fuente = Source(
                    name=cat["name"],
                    rss_url=cat["rss"],
                    url=cat["url"],
                    category=cat["category"],
                    is_active=True
                )
                db.add(nueva_fuente)
                await db.flush()
                await db.refresh(nueva_fuente)
                
                print(f"✅ {cat['name']} creada (ID: {nueva_fuente.id})")
                
                # Crear perfil con los selectores aprendidos
                if analisis and analisis.get('confidence_score', 0) >= 0.6:
                    perfil = SourceProfile(
                        source_id=nueva_fuente.id,
                        title_selector=analisis.get('title_selector'),
                        body_selector=analisis.get('body_selector'),
                        image_selector=analisis.get('image_selector'),
                        date_selector=analisis.get('date_selector'),
                        author_selector=analisis.get('author_selector'),
                        confidence_score=analisis['confidence_score'],
                    )
                    db.add(perfil)
                    print(f"   ✅ Perfil aplicado (confidence: {analisis['confidence_score']:.0%})")
                
            except Exception as e:
                print(f"❌ Error agregando {cat['name']}: {e}")
        
        await db.commit()
        print(f"\n🎉 Todas las categorías fueron agregadas!")
        print(f"   Ya puedes ejecutar scraping desde el panel admin")

if __name__ == "__main__":
    asyncio.run(main())
