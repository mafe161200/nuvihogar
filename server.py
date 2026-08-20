from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import json
import os


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)


# ============================================================
# CARGAR DATOS
# ============================================================

def cargar_arriendos():

    ruta = os.path.join(
        BASE_DIR,
        "data",
        "arriendos.json"
    )

    try:

        with open(
            ruta,
            "r",
            encoding="utf-8"
        ) as archivo:

            data = json.load(archivo)

        if not isinstance(data, list):
            return []

        return data

    except FileNotFoundError:

        print("ERROR: No existe data/arriendos.json")

        return []

    except json.JSONDecodeError as error:

        print(
            f"ERROR: arriendos.json no es un JSON válido: {error}"
        )

        return []

    except Exception as error:

        print(
            f"ERROR leyendo arriendos.json: {error}"
        )

        return []


# ============================================================
# FRONTEND
# ============================================================

@app.route("/")
def inicio():

    return send_from_directory(
        BASE_DIR,
        "index.html"
    )


@app.route("/styles.css")
def styles():

    return send_from_directory(
        BASE_DIR,
        "styles.css"
    )


@app.route("/app.js")
def javascript():

    return send_from_directory(
        BASE_DIR,
        "app.js"
    )


# ============================================================
# API - ARRIENDOS
# ============================================================

@app.route("/api/arriendos")
def obtener_arriendos():

    try:

        arriendos = cargar_arriendos()

        return jsonify(arriendos)

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500


# ============================================================
# API - ESTADÍSTICAS
# ============================================================

@app.route("/api/estadisticas")
def obtener_estadisticas():

    try:

        arriendos = cargar_arriendos()

        if not arriendos:

            return jsonify({
                "cantidad": 0,
                "promedio": 0,
                "minimo": 0,
                "maximo": 0,
                "precio_m2": 0
            })

        canones = []

        precios_m2 = []

        for inmueble in arriendos:

            canon = inmueble.get("canon")

            if isinstance(canon, (int, float)) and canon > 0:

                canones.append(canon)

            precio_m2 = inmueble.get("precio_m2")

            if isinstance(
                precio_m2,
                (int, float)
            ) and precio_m2 > 0:

                precios_m2.append(precio_m2)

        promedio = (
            sum(canones) / len(canones)
            if canones
            else 0
        )

        precio_m2_promedio = (
            sum(precios_m2) / len(precios_m2)
            if precios_m2
            else 0
        )

        return jsonify({

            "cantidad": len(arriendos),

            "promedio": round(
                promedio
            ),

            "minimo": min(canones)
            if canones
            else 0,

            "maximo": max(canones)
            if canones
            else 0,

            "precio_m2": round(
                precio_m2_promedio
            )

        })

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500


# ============================================================
# EJECUTAR SERVIDOR
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 50)
    print("        ARRIENDOS CALI - SERVIDOR")
    print("=" * 50)
    print()
    print(
        "Frontend:"
    )
    print(
        "http://127.0.0.1:5000"
    )
    print()
    print(
        "API:"
    )
    print(
        "http://127.0.0.1:5000/api/arriendos"
    )
    print()
    print(
        "CSS:"
    )
    print(
        "http://127.0.0.1:5000/styles.css"
    )
    print()
    print(
        "JavaScript:"
    )
    print(
        "http://127.0.0.1:5000/app.js"
    )
    print()
    print("=" * 50)
    print()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )
    