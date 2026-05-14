#!/usr/bin/env python3
"""
Script para agregar la fuente de Salud de Diario Libre con scraping HTML.
Analiza el HTML, aprende los selectores y agrega la fuente a la BD.
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

# URL de la categoría Salud
SALUD_URL = "https://www.diariolibre.com/actualidad/salud"
SALUD_RSS = "https://www.diariolibre.com/rss/salud.xml"

async def main():
    print("🔍 Analizando HTML de Diario Libre - Salud...")
    
    # 1. Descargar el HTML
    try:
        response = requests.get(SALUD_URL, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BylineBot/1.0)"
        })
        response.raise_for_status()
        html = response.text
        print(f"✅ HTML descargado ({len(html)} caracteres)")
    except Exception as e:
        print(f"❌ Error descargando HTML: {e}")
        return
    
    # 2. Analizar con el profiler
    profiler = HTMLProfiler()
    
    # Necesitamos analizar un artículo individual, no la página de categoría
    # Extraer el primer enlace de artículo de la página
    soup = BeautifulSoup(html, "html.parser")
    
    # Buscar enlaces a artículos (patrón típico de Diario Libre)
    article_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/actualidad/salud/" in href and href.startswith("http"):
            article_link = href
            break
    
    if not article_link:
        print("⚠️ No se encontró enlace a artículo, usando URL de categoría")
        article_link = SALUD_URL
    
    print(f"📄 URL de artículo para análisis: {article_link}")
    
    # Descargar artículo individual
    try:
        article_response = requests.get(article_link, timeout=30, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BylineBot/1.0)"
        })
        article_response.raise_for_status()
        article_html = article_response.text
        
        # Analizar el artículo
        analisis = profiler.analyze(article_html, article_link)
        
        print(f"\n📊 Resultados del análisis:")
        print(f"   Title selector: {analisis['title_selector']}")
        print(f"   Body selector: {analisis['body_selector']}")
        print(f"   Image selector: {analisis['image_selector']}")
        print(f"   Date selector: {analisis['date_selector']}")
        print(f"   Author selector: {analisis['author_selector']}")
        print(f"   Confidence: {analisis['confidence_score']:.0%}")
        
        if analisis['confidence_score'] < 0.7:
            print("\n⚠️  Advertencia: Confidence bajo (< 70%)")
            print("   Los selectores pueden no ser precisos")
        
    except Exception as e:
        print(f"❌ Error analizando artículo: {e}")
        print("   Continuando sin perfil de scraping...")
        analisis = None
    
    # 3. Agregar a la base de datos
    print(f"\n💾 Agregando fuente a la base de datos...")
    
    try:
        async with AsyncSessionLocal() as db:
            # Verificar si ya existe
            from sqlalchemy import select
            result = await db.execute(
                select(Source).where(Source.rss_url == SALUD_RSS)
            )
            existente = result.scalar_one_or_none()
            
            if existente:
                print(f"⚠️  La fuente ya existe (ID: {existente.id})")
                print(f"   Nombre: {existente.name}")
                return
            
            # Crear fuente
            nueva_fuente = Source(
                name="Diario Libre - Salud",
                rss_url=SALUD_RSS,
                url=SALUD_URL,
                category="salud",
                is_active=True
            )
            db.add(nueva_fuente)
            await db.flush()
            await db.refresh(nueva_fuente)
            
            print(f"✅ Fuente creada (ID: {nueva_fuente.id})")
            
            # Crear perfil si el análisis fue exitoso
            if analisis and analisis['confidence_score'] >= 0.7:
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
                print(f"✅ Perfil de scraping creado (confidence: {analisis['confidence_score']:.0%})")
            
            await db.commit()
            print(f"\n🎉 Fuente agregada exitosamente!")
            print(f"   Puedes ejecutar scraping manual desde el panel admin")
            
    except Exception as e:
        print(f"❌ Error guardando en BD: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
