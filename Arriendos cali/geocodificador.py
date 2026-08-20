import json
import time
import requests
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================
ARCHIVO_JSON = Path("data/arriendos.json")
CACHE_COORDENADAS = Path("data/cache_coordenadas.json")

def cargar_json(ruta):
    if ruta.exists():
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return {} if "cache" in ruta.name else []

def guardar_json(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def main():
    print("=" * 50)
    print("       GEOCODIFICADOR DE INMUEBLES (CORREGIDO)")
    print("=" * 50)
    
    inmuebles = cargar_json(ARCHIVO_JSON)
    cache = cargar_json(CACHE_COORDENADAS)
    
    # OpenStreetMap requiere un User-Agent identificable
    headers = {"User-Agent": "BuscadorArriendosCali/1.0"}
    actualizados = 0
    
    for inv in inmuebles:
        # Si ya tiene coordenadas válidas, lo saltamos
        if "lat" in inv and "lng" in inv and inv["lat"]:
            continue
        
        barrio = inv.get("barrio")
        ubicacion = inv.get("ubicacion")
        ciudad = inv.get("ciudad")
        
        # Prioridad de búsqueda: Barrio -> Ubicación -> Ciudad
        termino = barrio if barrio else ubicacion
        if not termino:
            termino = ciudad
            
        if not termino:
            continue # Si definitivamente no hay datos, saltamos
            
        # Para mayor precisión, si la ciudad no está escrita en el término, se la sumamos
        if ciudad and ciudad.lower() not in termino.lower():
            query = f"{termino}, {ciudad}, Valle del Cauca, Colombia"
        else:
            query = f"{termino}, Valle del Cauca, Colombia"
        
        if query in cache:
            if cache[query]:
                inv["lat"] = cache[query]["lat"]
                inv["lng"] = cache[query]["lng"]
            continue
            
        print(f"📍 Buscando coordenadas para: {termino}...")
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1"
        
        try:
            respuesta = requests.get(url, headers=headers, timeout=10)
            data = respuesta.json()
            
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                inv["lat"] = lat
                inv["lng"] = lng
                cache[query] = {"lat": lat, "lng": lng}
                print(f"   ✓ Encontrado: {lat}, {lng}")
            else:
                # PLAN B: Si no encontró el barrio, poner el pin en el centro de la ciudad
                if ciudad and termino != ciudad:
                    print("   - Intentando ubicar en el centro de la ciudad...")
                    query_respaldo = f"{ciudad}, Valle del Cauca, Colombia"
                    url_respaldo = f"https://nominatim.openstreetmap.org/search?q={query_respaldo}&format=json&limit=1"
                    resp_respaldo = requests.get(url_respaldo, headers=headers, timeout=10)
                    data_respaldo = resp_respaldo.json()
                    
                    if data_respaldo:
                        lat = float(data_respaldo[0]["lat"])
                        lng = float(data_respaldo[0]["lon"])
                        inv["lat"] = lat
                        inv["lng"] = lng
                        cache[query] = {"lat": lat, "lng": lng}
                        print(f"   ✓ Encontrado (Centro): {lat}, {lng}")
                    else:
                        cache[query] = None
                        print("   ✗ No encontrado.")
                    time.sleep(1.5)
                else:
                    cache[query] = None
                    print("   ✗ No encontrado en el mapa.")
                
            actualizados += 1
            guardar_json(CACHE_COORDENADAS, cache)
            time.sleep(1.5) # Pausa obligatoria para que no nos bloqueen la IP
            
        except Exception as e:
            print(f"   ! Error consultando API: {e}")
            time.sleep(2)
            
    if actualizados > 0:
        guardar_json(ARCHIVO_JSON, inmuebles)
        print(f"\n¡Listo! Se añadieron coordenadas a {actualizados} propiedades.")
    else:
        print("\nTodos los inmuebles mapeables ya tienen sus coordenadas.")

if __name__ == "__main__":
    main()