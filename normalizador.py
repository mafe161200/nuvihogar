import json
import re
from pathlib import Path

ARCHIVO_DATOS = Path("data/arriendos.json")

# Palabras prohibidas ampliadas para inmuebles comerciales y no residenciales
PALABRAS_PROHIBIDAS = [
    "local", "locales", "oficina", "oficinas", "bodega", "bodegas", 
    "lote", "lotes", "consultorio", "consultorios", "edificio", "edificios", 
    "terreno", "terrenos", "finca", "fincas", "comercial", "parqueadero", 
    "garaje", "deposito", "habitacion", "habitaciones", "cuarto"
]

CANON_MINIMO = 200000
CANON_MAXIMO = 3000000

def es_comercial(texto):
    if not texto:
        return False
    # Limpiamos puntuación y pasamos a minúsculas
    texto_limpio = re.sub(r'[^\w\s]', ' ', str(texto).lower())
    palabras = texto_limpio.split()
    return any(p in PALABRAS_PROHIBIDAS for p in palabras)

def main():
    if not ARCHIVO_DATOS.exists():
        print("No se encontró el archivo data/arriendos.json")
        return

    with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
        datos = json.load(f)

    limpios = []
    descartados = 0

    for item in datos:
        titulo = item.get("titulo", "")
        tipo = item.get("tipo_inmueble", item.get("tipo", ""))
        barrio = item.get("barrio", "")
        ubicacion = item.get("ubicacion", "")

        # 1. Filtro estricto: Descartar si alguna propiedad contiene términos comerciales
        texto_evaluar = f"{titulo} {tipo} {barrio} {ubicacion}"
        if es_comercial(texto_evaluar):
            descartados += 1
            continue

        # 2. Normalización de precio
        try:
            canon = int(item.get("canon", 0))
        except (ValueError, TypeError):
            canon = 0

        if 0 < canon < 10000:
            canon = canon * 1000

        # Filtro de rango de precio residencial
        if canon < CANON_MINIMO or canon > CANON_MAXIMO:
            descartados += 1
            continue

        item["canon"] = canon

        # Categorización estricta
        titulo_lower = str(titulo).lower()
        if "casa" in titulo_lower:
            item["tipo_inmueble"] = "Casa"
        elif "apartaestudio" in titulo_lower or "aptoestudio" in titulo_lower:
            item["tipo_inmueble"] = "Apartaestudio"
        else:
            item["tipo_inmueble"] = "Apartamento"

        limpios.append(item)

    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(limpios, f, ensure_ascii=False, indent=4)

    print(f"✓ Normalización exitosa: {len(limpios)} inmuebles residenciales conservados. {descartados} comerciales/basura eliminados.")

if __name__ == "__main__":
    main()