import json
import re
import time
import os
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# CONFIGURACIÓN
# ============================================================
ARCHIVO_DATOS = Path(__file__).resolve().parent.parent / "data" / "arriendos.json"

MUNICIPIOS = {
    "Cali": "https://listado.mercadolibre.com.co/inmuebles/arriendo/valle-del-cauca/cali/",
    "Jamundí": "https://listado.mercadolibre.com.co/inmuebles/arriendo/valle-del-cauca/jamundi/",
    "Palmira": "https://listado.mercadolibre.com.co/inmuebles/arriendo/valle-del-cauca/palmira/",
    "Yumbo": "https://listado.mercadolibre.com.co/inmuebles/arriendo/valle-del-cauca/yumbo/",
    "Candelaria": "https://listado.mercadolibre.com.co/inmuebles/arriendo/valle-del-cauca/candelaria/"
}

CANON_MAXIMO = 2000000

# ============================================================
# UTILIDADES
# ============================================================
def cargar_arriendos():
    if ARCHIVO_DATOS.exists():
        with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def guardar_arriendos(datos):
    ARCHIVO_DATOS.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def extraer_numero(texto):
    if not texto: return 0
    numeros = re.findall(r'\d+', texto.replace('.', '').replace(',', ''))
    return int(numeros[0]) if numeros else 0

def extraer_area(texto):
    match = re.search(r'(\d+)\s*m', texto, re.IGNORECASE)
    return int(match.group(1)) if match else None

# ============================================================
# EXTRACCIÓN POR MUNICIPIO
# ============================================================
def procesar_municipio(page, municipio, url_base):
    print(f"\nConsultando MercadoLibre - {municipio}...")
    publicaciones = []
    
    for pagina in range(3):
        url = url_base
        if pagina > 0:
            url += f"_Desde_{pagina * 48 + 1}_NoIndex_True"
            
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # PAUSA LARGA EN LA PRIMERA PÁGINA
            if pagina == 0:
                print("   - (Verifica la ventana. Esperando 10 segundos...)")
                time.sleep(10)
            else:
                time.sleep(4)
            
            # Bajar por la página para cargar todas las fotos (lazy loading)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight/1.5)")
            time.sleep(1)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # TODOTERRENO: Busca tanto el formato viejo como el nuevo de MercadoLibre
            resultados = soup.find_all("li", class_="ui-search-layout__item")
            if not resultados:
                resultados = soup.find_all("div", class_=re.compile(r"poly-card"))
            
            if not resultados:
                print("   - No hay más resultados o no se encontró la estructura de inmuebles.")
                break
                
            for item in resultados:
                # Titulo
                titulo_elem = item.find("h2")
                titulo = titulo_elem.text.strip() if titulo_elem else "Inmueble en arriendo"
                
                # Enlace
                enlace_elem = item.find("a")
                if not enlace_elem or "href" not in enlace_elem.attrs: continue
                url_pub = enlace_elem["href"].split("#")[0]
                
                # Precio
                precio_elem = item.find("span", class_="andes-money-amount__fraction")
                canon = extraer_numero(precio_elem.text) if precio_elem else 0
                
                if canon > CANON_MAXIMO: continue
                    
                # Ubicación
                ubicacion_elem = item.find("span", class_=re.compile(r"location"))
                ubicacion = ubicacion_elem.text.strip() if ubicacion_elem else municipio
                barrio = ubicacion.split(",")[0].strip() if "," in ubicacion else ""
                
                # Imagen
                img_elem = item.find("img")
                imagen = ""
                if img_elem:
                    imagen = img_elem.get("data-src") or img_elem.get("src", "")
                
                # Área y Habitaciones (busca en cualquier texto descriptivo de la tarjeta)
                area, habitaciones = None, None
                textos_atributos = item.find_all("span", class_=re.compile(r"poly-attributes|ui-search-card"))
                if not textos_atributos:
                    textos_atributos = item.find_all("li")
                    
                for attr in textos_atributos:
                    texto_attr = attr.text.lower()
                    if "m²" in texto_attr or "m2" in texto_attr: 
                        area = extraer_area(texto_attr)
                    elif "hab" in texto_attr or "alcoba" in texto_attr: 
                        habitaciones = extraer_numero(texto_attr)
                        
                tipo = "Apartamento"
                if "casa" in titulo.lower(): tipo = "Casa"
                if "apartaestudio" in titulo.lower() or "aptoestudio" in titulo.lower(): tipo = "Apartaestudio"
                
                publicaciones.append({
                    "fuente": "MercadoLibre",
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
                
        except Exception as e:
            print(f" Error en página {pagina + 1}: {e}")
            break
            
    print(f" ✓ Se capturaron {len(publicaciones)} opciones válidas.")
    return publicaciones

# ============================================================
# BLOQUE PRINCIPAL
# ============================================================
def main():
    print("=" * 50)
    print("    SCRAPER MERCADOLIBRE (NUEVA VERSIÓN) - CALI")
    print("=" * 50)
    
    existentes = cargar_arriendos()
    urls_existentes = {item.get("url_original") for item in existentes if item.get("url_original")}
    nuevos_inmuebles = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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