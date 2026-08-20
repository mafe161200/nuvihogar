import json
import re
import time
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# CONFIGURACIÓN
# ============================================================
ARCHIVO_DATOS = Path(__file__).resolve().parent.parent / "data" / "arriendos.json"

MUNICIPIOS = {
    "Cali": "https://www.ciencuadras.com/arriendo/inmuebles/cali/cali",
    "Jamundí": "https://www.ciencuadras.com/arriendo/inmuebles/valle-del-cauca/jamundi",
    "Palmira": "https://www.ciencuadras.com/arriendo/inmuebles/valle-del-cauca/palmira",
    "Yumbo": "https://www.ciencuadras.com/arriendo/inmuebles/valle-del-cauca/yumbo",
    "Candelaria": "https://www.ciencuadras.com/arriendo/inmuebles/valle-del-cauca/candelaria"
}

CANON_MINIMO = 300000
CANON_MAXIMO = 15000000 # Aumentamos el tope a 15 millones para no perder apartamentos costosos

PALABRAS_PROHIBIDAS = [
    "oficina", "local", "bodega", "lote", "consultorio", "edificio", 
    "terreno", "finca", "comercial", "parqueadero", "garaje", "deposito"
]

# ============================================================
# UTILIDADES
# ============================================================
def cargar_arriendos():
    if ARCHIVO_DATOS.exists():
        try:
            with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def guardar_arriendos(datos):
    ARCHIVO_DATOS.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def extraer_numero(texto):
    if not texto: return 0
    
    # 1. Buscar ESPECÍFICAMENTE números que tengan el signo $ antes (ej. $ 3.000.000)
    match_precio = re.search(r'\$\s*([\d\.\,]+)', str(texto))
    if match_precio:
        limpio = re.sub(r'[^\d]', '', match_precio.group(1))
        if limpio: return int(limpio)

    # 2. Si la página no usa $, hacemos el fallback original
    limpio = re.sub(r'[^\d]', ' ', str(texto))
    numeros = [int(n) for n in limpio.split() if n.strip()]
    if not numeros: return 0
    
    for n in numeros:
        if CANON_MINIMO <= n <= CANON_MAXIMO:
            return n
    return max(numeros)

def extraer_area(texto):
    match = re.search(r'(\d+)\s*m', str(texto), re.IGNORECASE)
    return int(match.group(1)) if match else None

def es_comercial(texto):
    if not texto: return False
    texto_lc = str(texto).lower()
    return any(p in texto_lc for p in PALABRAS_PROHIBIDAS)

# ============================================================
# EXTRACCIÓN POR MUNICIPIO Y PAGINACIÓN
# ============================================================
def procesar_municipio(page, municipio, url_base):
    print(f"\nConsultando Ciencuadras - {municipio}...")
    publicaciones = []
    
    for num_pagina in range(1, 6):
        url = url_base if num_pagina == 1 else f"{url_base}?page={num_pagina}"
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            cards = soup.find_all("div", class_=re.compile(r"card|property|item", re.I))
            if not cards:
                cards = soup.find_all("article")

            if not cards:
                break

            capturados_pagina = 0
            for card in cards:
                texto_card = card.text

                if es_comercial(texto_card):
                    continue

                link_elem = card.find("a", href=True)
                if not link_elem: continue
                url_pub = link_elem["href"]
                if not url_pub.startswith("http"):
                    url_pub = "https://www.ciencuadras.com" + url_pub

                titulo_elem = card.find(["h2", "h3", "h4", "p"], class_=re.compile(r"title|type|inmueble", re.I))
                titulo = titulo_elem.text.strip() if titulo_elem else "Inmueble en arriendo"
                if es_comercial(titulo):
                    continue

                precio_elem = card.find(class_=re.compile(r"price|precio|value|canon", re.I))
                canon = extraer_numero(precio_elem.text if precio_elem else texto_card)

                if canon < CANON_MINIMO or canon > CANON_MAXIMO:
                    continue

                ubicacion_elem = card.find(class_=re.compile(r"location|barrio|address|city", re.I))
                ubicacion = ubicacion_elem.text.strip() if ubicacion_elem else municipio
                barrio = ubicacion.split(",")[0].strip() if "," in ubicacion else ubicacion

                img_elem = card.find("img")
                imagen = ""
                if img_elem:
                    imagen = img_elem.get("src") or img_elem.get("data-src", "")

                textos_card_lower = texto_card.lower()
                area = extraer_area(textos_card_lower)
                habitaciones = None
                
                hab_match = re.search(r'(\d+)\s*(hab|alcoba|dormitorio)', textos_card_lower)
                if hab_match:
                    habitaciones = int(hab_match.group(1))

                tipo = "Apartamento"
                if "casa" in titulo.lower(): tipo = "Casa"
                elif "apartaestudio" in titulo.lower() or "aptoestudio" in titulo.lower(): tipo = "Apartaestudio"

                publicaciones.append({
                    "fuente": "Ciencuadras",
                    "municipio": municipio,
                    "ciudad": municipio,
                    "tipo_inmueble": tipo,
                    "barrio": barrio,
                    "ubicacion": ubicacion,
                    "canon": canon,
                    "area_m2": area,
                    "habitaciones": habitaciones,
                    "url_original": url_pub,
                    "imagen_principal": imagen,
                    "titulo": titulo,
                    "fecha_recoleccion": datetime.now().isoformat(timespec="seconds")
                })
                capturados_pagina += 1

            if capturados_pagina == 0 and num_pagina > 1:
                break

        except Exception as e:
            print(f"   - Error cargando página {num_pagina} de {municipio}: {e}")
            break

    print(f" ✓ Se capturaron {len(publicaciones)} inmuebles residenciales en {municipio}.")
    return publicaciones

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 50)
    print("    SCRAPER CIENCUADRAS (MULTIPÁGINA RESIDENCIAL) - CALI")
    print("=" * 50)

    existentes = cargar_arriendos()
    urls_existentes = {item.get("url_original") for item in existentes if item.get("url_original")}
    nuevos_inmuebles = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for municipio, url in MUNICIPIOS.items():
            resultados = procesar_municipio(page, municipio, url)
            for res in resultados:
                if res["url_original"] not in urls_existentes:
                    nuevos_inmuebles.append(res)
                    urls_existentes.add(res["url_original"])

        browser.close()

    if nuevos_inmuebles:
        max_id = max([item.get("id", 0) for item in existentes if isinstance(item.get("id"), int)]) if existentes else 0
        for i, item in enumerate(nuevos_inmuebles, 1):
            item["id"] = max_id + i

        existentes.extend(nuevos_inmuebles)
        guardar_arriendos(existentes)
        print(f"\n¡Éxito! Se añadieron {len(nuevos_inmuebles)} inmuebles NUEVOS a tu base de datos.")
    else:
        print("\nNo se encontraron inmuebles nuevos.")

if __name__ == "__main__":
    main()
