import json
import re
import time
import random
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_DATOS = BASE_DIR / "data" / "arriendos.json"

CANON_MINIMO = 300000
CANON_MAXIMO = 2000000

# Filtro estricto para descartar locales, oficinas, bodegas, etc.
PROHIBIDAS = ["oficina", "local", "bodega", "lote", "consultorio", "comercial", "edificio", "finca", "proyecto"]

def es_comercial(texto):
    if not texto: return False
    t = str(texto).lower()
    return any(p in t for p in PROHIBIDAS)

def extraer_numero(texto):
    if not texto: return 0
    # Extraemos todos los números del texto eliminando puntos y comas
    numeros = re.findall(r'\d+', str(texto).replace('.', '').replace(',', '').replace("'", ""))
    for n in numeros:
        val = int(n)
        # El primer valor que caiga en el rango de un arriendo real de vivienda se toma como el Canon
        if CANON_MINIMO <= val <= CANON_MAXIMO:
            return val
    return 0

def extraer_area(texto):
    m = re.search(r'(\d+)\s*m', str(texto), re.I)
    return int(m.group(1)) if m else None

def extraer_habs(texto):
    m = re.search(r'(\d+)\s*(hab|alcoba|dormitorio)', str(texto), re.I)
    return int(m.group(1)) if m else None

def extraer_banos(texto):
    m = re.search(r'(\d+)\s*(baño|bano)', str(texto), re.I)
    return int(m.group(1)) if m else None

def procesar_portal(page, url_base, fuente, ciudad, max_paginas=4):
    resultados = []
    
    # Navegamos página 1, 2, 3 y 4 de los resultados
    for i in range(1, max_paginas + 1):
        url = f"{url_base}?page={i}" if i > 1 else url_base
        print(f" -> {fuente} | {ciudad} | Página {i}")
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            # Simular scroll humano para que carguen las fotos y los precios
            page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

            soup = BeautifulSoup(page.content(), "html.parser")
            
            # Buscamos ÚNICAMENTE los enlaces que van a una ficha técnica individual
            links = soup.find_all('a', href=re.compile(r'/inmueble/'))
            
            capturados_pagina = 0
            for link in links:
                url_pub = link['href']
                if not url_pub.startswith("http"):
                    dominio = "https://www.ciencuadras.com" if fuente == "Ciencuadras" else "https://www.metrocuadrado.com"
                    url_pub = dominio + url_pub
                
                # Evitar duplicados
                if any(r['url_original'] == url_pub for r in resultados):
                    continue

                # Buscar el contenedor de la tarjeta para extraer la info completa
                card = link.find_parent(['div', 'article', 'li'])
                if not card: card = link

                texto_card = card.text

                # Filtro comercial
                if es_comercial(texto_card) or es_comercial(link.text):
                    continue

                # Extracción del precio real publicado
                canon = extraer_numero(texto_card)
                if canon == 0:
                    continue

                titulo = link.text.strip() or f"Inmueble en {ciudad}"
                
                tipo = "Apartamento"
                if "casa" in titulo.lower() or "casa" in url_pub.lower(): tipo = "Casa"
                elif "apartaestudio" in titulo.lower() or "estudio" in url_pub.lower(): tipo = "Apartaestudio"

                img_elem = card.find("img")
                imagen = img_elem.get("src") or img_elem.get("data-src") if img_elem else ""

                resultados.append({
                    "fuente": fuente,
                    "municipio": ciudad,
                    "ciudad": ciudad,
                    "barrio": ciudad, 
                    "ubicacion": f"{ciudad}, Valle del Cauca",
                    "tipo_inmueble": tipo,
                    "titulo": titulo,
                    "canon": canon,
                    "area_m2": extraer_area(texto_card),
                    "habitaciones": extraer_habs(texto_card),
                    "banos": extraer_banos(texto_card),
                    "parqueadero": "parqueadero" in texto_card.lower() or "garaje" in texto_card.lower(),
                    "url_original": url_pub, # ¡Este es el enlace al anuncio exacto!
                    "imagen_principal": imagen,
                    "fecha_recoleccion": datetime.now().isoformat(timespec="seconds")
                })
                capturados_pagina += 1
            
            print(f"    ✓ Anuncios extraídos: {capturados_pagina}")
            if capturados_pagina == 0:
                break # Si la página está vacía, no sigue buscando en la siguiente

        except Exception as e:
            print(f"    - Error en página {i}: {e}")
            break
            
    return resultados

def main():
    print("="*60)
    print(" EXTRACCIÓN MASIVA: CIENCUADRAS + METROCUADRADO ")
    print("="*60)

    PORTALES = [
        ("Ciencuadras", "Cali", "https://www.ciencuadras.com/arriendo/cali"),
        ("Ciencuadras", "Jamundí", "https://www.ciencuadras.com/arriendo/jamundi"),
        ("Metrocuadrado", "Cali", "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/cali/"),
        ("Metrocuadrado", "Palmira", "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/palmira/")
    ]

    todos_resultados = []
    urls_vistas = set()

    with sync_playwright() as p:
        # Esto soluciona el error 'spawn EFTYPE', obligando a usar tu Chrome o Edge nativo
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            try:
                browser = p.chromium.launch(channel="msedge", headless=True)
            except Exception:
                browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        for fuente, ciudad, url_base in PORTALES:
            res = procesar_portal(page, url_base, fuente, ciudad, max_paginas=4)
            for r in res:
                if r['url_original'] not in urls_vistas:
                    urls_vistas.add(r['url_original'])
                    todos_resultados.append(r)

        browser.close()

    # Asignamos ID y coordenadas aproximadas a cada inmueble para el mapa
    for i, item in enumerate(todos_resultados, 1):
        item["id"] = i
        if item["ciudad"] == "Cali": lat, lng = 3.4516, -76.5320
        elif item["ciudad"] == "Jamundí": lat, lng = 3.2680, -76.5380
        elif item["ciudad"] == "Palmira": lat, lng = 3.5350, -76.3000
        else: lat, lng = 3.4516, -76.5320
        
        # Le damos una dispersión aleatoria al rededor de la ciudad para que los pines no queden uno encima de otro
        item["lat"] = round(lat + random.uniform(-0.045, 0.045), 6)
        item["lng"] = round(lng + random.uniform(-0.045, 0.045), 6)

    ARCHIVO_DATOS.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(todos_resultados, f, ensure_ascii=False, indent=4)

    print(f"\n✓ ¡Proceso Terminado! Se recolectaron un total de {len(todos_resultados)} anuncios individuales reales.")

if __name__ == "__main__":
    main()