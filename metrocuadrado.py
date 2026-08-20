import json
import re
import time
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURACIÓN
# ============================================================
ARCHIVO_DATOS = Path(__file__).resolve().parent.parent / "data" / "arriendos.json"

URLS = {
    "Cali": "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/cali/",
    "Jamundí": "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/jamundi/",
    "Palmira": "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/palmira/",
    "Yumbo": "https://www.metrocuadrado.com/apartamento-casa-apartaestudio/arriendo/yumbo/"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

CANON_MINIMO = 300000
CANON_MAXIMO = 2000000

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
    numeros = re.findall(r'\d+', str(texto).replace('.', '').replace(',', ''))
    if not numeros: return 0
    for n in numeros:
        val = int(n)
        if CANON_MINIMO <= val <= CANON_MAXIMO:
            return val
    return max([int(n) for n in numeros])

def es_comercial(texto):
    if not texto: return False
    texto_lc = str(texto).lower()
    return any(p in texto_lc for p in PALABRAS_PROHIBIDAS)

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 50)
    print("    SCRAPER METROCUADRADO (LIGHTWEIGHT) - CALI")
    print("=" * 50)

    existentes = cargar_arriendos()
    urls_existentes = {item.get("url_original") for item in existentes if item.get("url_original")}
    nuevos = []

    for ciudad, url in URLS.items():
        print(f"\nConsultando Metrocuadrado - {ciudad}...")
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"   - Estado HTTP {response.status_code}. Omitiendo {ciudad}.")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.find_all(["article", "div", "li"], class_=re.compile(r"m2-card|real-estate-card|card|property", re.I))

            capturados = 0
            for card in cards:
                texto_card = card.text

                # 1. Descartar si es inmueble comercial
                if es_comercial(texto_card):
                    continue

                # 2. Enlace
                link = card.find("a", href=True)
                if not link: continue
                url_pub = link["href"]
                if not url_pub.startswith("http"):
                    url_pub = "https://www.metrocuadrado.com" + url_pub

                if url_pub in urls_existentes: continue

                titulo = link.text.strip() if link.text.strip() else "Inmueble en arriendo"
                if es_comercial(titulo):
                    continue

                # 3. Precio
                precio_elem = card.find(class_=re.compile(r"price|valor|precio|canon", re.I))
                canon = extraer_numero(precio_elem.text if precio_elem else texto_card)

                if canon < CANON_MINIMO or canon > CANON_MAXIMO:
                    continue

                # 4. Imagen
                img_elem = card.find("img")
                imagen = ""
                if img_elem:
                    imagen = img_elem.get("src") or img_elem.get("data-src", "")

                tipo = "Apartamento"
                if "casa" in titulo.lower(): tipo = "Casa"
                elif "apartaestudio" in titulo.lower() or "aptoestudio" in titulo.lower(): tipo = "Apartaestudio"

                item = {
                    "fuente": "Metrocuadrado",
                    "municipio": ciudad,
                    "ciudad": ciudad,
                    "tipo_inmueble": tipo,
                    "barrio": ciudad,
                    "ubicacion": f"{ciudad}, Valle del Cauca",
                    "canon": canon,
                    "area_m2": None,
                    "habitaciones": None,
                    "url_original": url_pub,
                    "imagen_principal": imagen,
                    "titulo": titulo,
                    "fecha_recoleccion": datetime.now().isoformat(timespec="seconds")
                }

                nuevos.append(item)
                urls_existentes.add(url_pub)
                capturados += 1

            print(f" ✓ Se capturaron {capturados} inmuebles residenciales en {ciudad}.")

        except Exception as e:
            print(f"   - Error procesando {ciudad}: {e}")

    if nuevos:
        max_id = max([i.get("id", 0) for i in existentes if isinstance(i.get("id"), int)]) if existentes else 0
        for idx, item in enumerate(nuevos, 1):
            item["id"] = max_id + idx
        existentes.extend(nuevos)
        guardar_arriendos(existentes)
        print(f"\n¡Éxito! Se añadieron {len(nuevos)} inmuebles NUEVOS a tu base de datos.")
    else:
        print("\nNo se encontraron inmuebles nuevos.")

if __name__ == "__main__":
    main()