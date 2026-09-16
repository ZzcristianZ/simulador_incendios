"""
Ingesta de geografía real desde OpenStreetMap (Overpass API).

Objetivo: que la grilla del autómata celular no sea un rectángulo de
"zona urbana" inventado, sino que refleje los edificios, cuerpos de
agua, bosque y vías reales alrededor de la coordenada que el usuario
ingresó (por ejemplo, su propia casa).

Si la API de Overpass no responde (caída, timeout, sin internet), se
usa un terreno sintético de respaldo para que la simulación nunca se
detenga por completo.
"""

import math
import numpy as np
import requests

from simulador_automata import (
    ESTADO_VEGETACION_LIGERA,
    ESTADO_URBANO,
    ESTADO_AGUA,
    ESTADO_SIN_COMBUSTIBLE,
    ESTADO_VEGETACION_DENSA,
)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class GeografiaNoDisponibleError(Exception):
    """Se lanza cuando no fue posible obtener datos geográficos reales."""
    pass


def _metros_a_grados(lat_centro: float):
    """Factores de conversión metro -> grado en latitud/longitud locales."""
    grados_lat_por_m = 1.0 / 111_320.0
    grados_lon_por_m = 1.0 / (111_320.0 * math.cos(math.radians(lat_centro)))
    return grados_lat_por_m, grados_lon_por_m


def obtener_datos_geograficos(lat: float, lon: float, radio_m: float = 300.0) -> dict:
    """
    Consulta Overpass API por edificios, agua, bosque y vías dentro de un
    radio (en metros) alrededor de (lat, lon).

    Devuelve un dict con listas de polígonos (cada uno: lista de tuplas
    (lat, lon)) por categoría: 'edificios', 'agua', 'bosque', 'vias'.

    Lanza GeografiaNoDisponibleError si la consulta falla.
    """
    consulta = f"""
    [out:json][timeout:25];
    (
      way["building"](around:{radio_m},{lat},{lon});
      way["natural"="water"](around:{radio_m},{lat},{lon});
      way["landuse"="reservoir"](around:{radio_m},{lat},{lon});
      way["natural"="wood"](around:{radio_m},{lat},{lon});
      way["landuse"="forest"](around:{radio_m},{lat},{lon});
      way["highway"](around:{radio_m},{lat},{lon});
    );
    out geom;
    """

    try:
        respuesta = requests.post(OVERPASS_URL, data={"data": consulta}, timeout=30)
        respuesta.raise_for_status()
        datos = respuesta.json()
    except (requests.RequestException, ValueError) as error:
        raise GeografiaNoDisponibleError(str(error)) from error

    resultado = {"edificios": [], "agua": [], "bosque": [], "vias": []}

    for elemento in datos.get("elements", []):
        geometria = elemento.get("geometry")
        if not geometria:
            continue
        puntos = [(p["lat"], p["lon"]) for p in geometria]
        tags = elemento.get("tags", {})

        if "building" in tags:
            resultado["edificios"].append(puntos)
        elif tags.get("natural") == "water" or tags.get("landuse") == "reservoir":
            resultado["agua"].append(puntos)
        elif tags.get("natural") == "wood" or tags.get("landuse") == "forest":
            resultado["bosque"].append(puntos)
        elif "highway" in tags:
            resultado["vias"].append(puntos)

    return resultado


def _rasterizar_poligono(mascara, puntos_grilla, filas, columnas):
    """Marca en True las celdas cuyo centro cae dentro del polígono dado."""
    from matplotlib.path import Path

    if len(puntos_grilla) < 3:
        return
    ruta = Path(puntos_grilla)
    centros_i, centros_j = np.meshgrid(np.arange(filas), np.arange(columnas), indexing="ij")
    centros = np.column_stack([centros_j.ravel() + 0.5, centros_i.ravel() + 0.5])
    dentro = ruta.contains_points(centros).reshape(filas, columnas)
    mascara |= dentro


def rasterizar_geografia(datos_geo: dict, lat_centro: float, lon_centro: float,
                          filas: int, columnas: int, tam_celda_m: float):
    """
    Convierte los polígonos reales (en lat/lon) al sistema de coordenadas
    local de la grilla (fila, columna) y produce:
      - grid: matriz de estados iniciales (numpy int array)
      - celda_casa: (fila, col) de la celda central = coordenada exacta
        que ingresó el usuario (su casa / punto de interés).
    """
    grados_lat_por_m, grados_lon_por_m = _metros_a_grados(lat_centro)

    def latlon_a_celda(lat_p, lon_p):
        dist_m_y = (lat_p - lat_centro) / grados_lat_por_m
        dist_m_x = (lon_p - lon_centro) / grados_lon_por_m
        fila = (filas / 2.0) - (dist_m_y / tam_celda_m)
        col = (columnas / 2.0) + (dist_m_x / tam_celda_m)
        return fila, col

    grid = np.full((filas, columnas), ESTADO_VEGETACION_LIGERA, dtype=int)

    # Orden de "pintado": bosque -> agua -> vías -> edificios (los edificios
    # y el agua tienen prioridad visual/funcional sobre el resto).
    mascara_bosque = np.zeros((filas, columnas), dtype=bool)
    for poligono in datos_geo.get("bosque", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in poligono]
        _rasterizar_poligono(mascara_bosque, puntos, filas, columnas)
    grid[mascara_bosque] = ESTADO_VEGETACION_DENSA

    mascara_agua = np.zeros((filas, columnas), dtype=bool)
    for poligono in datos_geo.get("agua", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in poligono]
        _rasterizar_poligono(mascara_agua, puntos, filas, columnas)
    grid[mascara_agua] = ESTADO_AGUA

    mascara_vias = np.zeros((filas, columnas), dtype=bool)
    for via in datos_geo.get("vias", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in via]
        for (fila, col) in puntos:
            fi, ci = int(round(fila)), int(round(col))
            if 0 <= fi < filas and 0 <= ci < columnas:
                mascara_vias[fi, ci] = True
    grid[mascara_vias] = ESTADO_SIN_COMBUSTIBLE

    mascara_edificios = np.zeros((filas, columnas), dtype=bool)
    for poligono in datos_geo.get("edificios", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in poligono]
        _rasterizar_poligono(mascara_edificios, puntos, filas, columnas)
    grid[mascara_edificios] = ESTADO_URBANO

    celda_casa = (filas // 2, columnas // 2)

    return grid, celda_casa


def generar_terreno_sintetico(filas: int, columnas: int):
    """
    Terreno de respaldo (sin datos reales) usado solo si Overpass no está
    disponible. Reproduce, de forma simplificada, el patrón original del
    proyecto: una franja de agua y un bloque urbano.
    """
    grid = np.full((filas, columnas), ESTADO_VEGETACION_LIGERA, dtype=int)
    franja = slice(int(filas * 0.2), int(filas * 0.3))
    grid[franja, :] = ESTADO_AGUA
    bloque_f = slice(int(filas * 0.6), int(filas * 0.9))
    bloque_c = slice(int(columnas * 0.7), int(columnas * 0.9))
    grid[bloque_f, bloque_c] = ESTADO_URBANO
    celda_casa = (filas // 2, columnas // 2)
    return grid, celda_casa
