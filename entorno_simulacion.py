"""
Preparación del entorno de simulación.

Junta geografía real (OSM), elevación y clima evolutivo en funciones
puras, SIN ninguna dependencia de Streamlit. Esto permite:
  1) Probar esta lógica de forma aislada con datos simulados.
  2) Mantener app.py enfocado solo en la interfaz.
"""

import numpy as np
import requests
from scipy.ndimage import zoom

from ingesta_clima import (
    obtener_clima_tiempo_real,
    obtener_pronostico_horario,
    obtener_elevacion_grid,
    validar_y_sanitizar_clima,
)
from ingesta_geografica import (
    obtener_datos_geograficos,
    rasterizar_geografia,
    generar_terreno_sintetico,
    GeografiaNoDisponibleError,
)


def ajustar_elevacion_a_grilla(elevacion_gruesa: np.ndarray, filas: int, columnas: int) -> np.ndarray:
    """Interpola bilinealmente una malla de elevación gruesa (ej. 11x11)
    a la resolución fina de la grilla de simulación (filas x columnas)."""
    factor_f = filas / elevacion_gruesa.shape[0]
    factor_c = columnas / elevacion_gruesa.shape[1]
    resultado = zoom(elevacion_gruesa, (factor_f, factor_c), order=1)
    resultado = resultado[:filas, :columnas]
    if resultado.shape != (filas, columnas):
        pad_f = max(0, filas - resultado.shape[0])
        pad_c = max(0, columnas - resultado.shape[1])
        resultado = np.pad(resultado, ((0, pad_f), (0, pad_c)), mode="edge")[:filas, :columnas]
    return resultado


def preparar_terreno(lat: float, lon: float, radio_m: float, tam_celda_m: float,
                      incluir_pendiente: bool = True) -> dict:
    """
    Construye la grilla inicial (edificios, agua, bosque, vías reales si
    están disponibles) y, opcionalmente, el modelo de elevación fino.
    """
    filas = columnas = max(10, int(round((radio_m * 2) / tam_celda_m)))

    geografia_real = True
    try:
        datos_geo = obtener_datos_geograficos(lat, lon, radio_m)
        grid, celda_casa = rasterizar_geografia(datos_geo, lat, lon, filas, columnas, tam_celda_m)
    except GeografiaNoDisponibleError:
        geografia_real = False
        datos_geo = None
        grid, celda_casa = generar_terreno_sintetico(filas, columnas)

    elevacion_fina = None
    if incluir_pendiente:
        elevacion_gruesa = obtener_elevacion_grid(lat, lon, radio_m)
        if elevacion_gruesa is not None:
            elevacion_fina = ajustar_elevacion_a_grilla(elevacion_gruesa, filas, columnas)

    return {
        "filas": filas,
        "columnas": columnas,
        "grid": grid,
        "celda_casa": celda_casa,
        "elevacion": elevacion_fina,
        "datos_geo": datos_geo,
        "geografia_real": geografia_real,
    }


def preparar_serie_climatica(lat: float, lon: float, pasos_totales: int,
                              minutos_por_paso: int = 15, permitir_evolutivo: bool = True):
    """
    Devuelve (serie_climas, alertas, es_evolutivo):
      - serie_climas: lista de diccionarios de clima. Si es_evolutivo es
        True, cada hora simulada tiene su propio clima (pronóstico real);
        si es False, es una lista de un solo elemento (clima 'actual'
        repetido durante toda la corrida).
      - alertas: mensajes de variables faltantes/sustituidas (del primer
        punto de la serie).
    """
    es_evolutivo = False
    serie = None

    if permitir_evolutivo:
        horas_necesarias = min(48, max(2, (pasos_totales * minutos_por_paso) // 60 + 2))
        try:
            serie = obtener_pronostico_horario(lat, lon, horas=horas_necesarias)
            es_evolutivo = True
        except requests.RequestException:
            serie = None

    if serie is None:
        clima_actual = obtener_clima_tiempo_real(lat, lon)
        serie = [clima_actual]
        es_evolutivo = False

    serie_saneada = []
    alertas = []
    for i, clima in enumerate(serie):
        clima_ok, alertas_clima = validar_y_sanitizar_clima(clima)
        serie_saneada.append(clima_ok)
        if i == 0:
            alertas = alertas_clima

    return serie_saneada, alertas, es_evolutivo


def clima_en_paso(serie_climatica: list, paso: int, minutos_por_paso: int = 15) -> dict:
    """Selecciona el clima horario correspondiente a un paso de simulación
    (paso 1-indexado, cada paso dura `minutos_por_paso` minutos)."""
    idx = min(len(serie_climatica) - 1, ((paso - 1) * minutos_por_paso) // 60)
    return serie_climatica[idx]
