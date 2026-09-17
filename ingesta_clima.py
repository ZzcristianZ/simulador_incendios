import numpy as np
import requests
from geopy.geocoders import Nominatim

def obtener_coordenadas(nombre_lugar: str):
    """Convierte el nombre de una ubicación a latitud y longitud."""
    geolocator = Nominatim(user_agent="simulador_incendios")
    location = geolocator.geocode(nombre_lugar)
    if not location:
        raise ValueError(f"No se encontraron coordenadas para: '{nombre_lugar}'")
    return location.latitude, location.longitude

def validar_y_sanitizar_clima(clima):
    """
    Verifica las variables necesarias para el autómata de incendios.
    Si alguna variable falta o viene como None, asigna un valor estándar aproximado
    y genera una lista detallada con las variables faltantes.
    """
    if not isinstance(clima, dict):
        clima = {}

    clima_seguro = clima.copy()
    variables_faltantes = []

    # Esquema de variables requeridas: (Clave, Valor por defecto, Unidad, Nombre para el usuario)
    esquema = [
        ("temperatura", 25.0, "°C", "Temperatura ambiente"),
        ("humedad_relativa", 50.0, "%", "Humedad relativa"),
        ("viento_velocidad", 3.0, "m/s", "Velocidad del viento"),
        ("vpd", 1.2, "kPa", "Déficit de presión de vapor (VPD)"),
        ("humedad_suelo", 0.30, "m³/m³", "Humedad del suelo")
    ]

    for clave, val_defecto, unidad, nombre_humano in esquema:
        valor = clima_seguro.get(clave)
        if valor is None:
            clima_seguro[clave] = val_defecto
            variables_faltantes.append(f"• **{nombre_humano}**: No disponible. Se estimó en **{val_defecto} {unidad}**.")

    return clima_seguro, variables_faltantes

def obtener_clima_tiempo_real(lat: float, lon: float) -> dict:
    """Consulta Open-Meteo y retorna las 8 variables en unidades del SI."""
    url = "https://api.open-meteo.com/v1/forecast"
    
    parametros = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "vapour_pressure_deficit",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "precipitation",
            "shortwave_radiation",
            "soil_moisture_0_to_7cm"
        ]
    }
    
    respuesta = requests.get(url, params=parametros, timeout=10)
    respuesta.raise_for_status()
    datos = respuesta.json()["current"]
    
    # Estandarización de unidades (conversiones requeridas para física/fuego)
    clima = {
        "temperatura": datos["temperature_2m"],                     # °C
        "humedad_relativa": datos["relative_humidity_2m"],         # %
        "vpd": datos["vapour_pressure_deficit"],                   # kPa
        "viento_velocidad": datos["wind_speed_10m"] / 3.6,          # Conversión de km/h a m/s
        "viento_rafagas": datos["wind_gusts_10m"] / 3.6,           # Conversión de km/h a m/s
        "viento_direccion": datos["wind_direction_10m"],           # Grados (0° a 360°)
        "precipitacion": datos["precipitation"],                   # mm
        "radiacion_solar": datos["shortwave_radiation"],           # W/m²
        "humedad_suelo": datos["soil_moisture_0_to_7cm"]          # m³/m³ (índice 0 a 1)
    }
    
    return clima


def obtener_pronostico_horario(lat: float, lon: float, horas: int = 24) -> list:
    """
    Consulta el pronóstico horario de Open-Meteo (en vez de una sola foto
    del clima 'actual'). Devuelve una lista de diccionarios de clima (uno
    por hora, mismas claves/unidades que obtener_clima_tiempo_real), para
    que la simulación pueda usar condiciones que cambian en el tiempo en
    vez de un único valor estático repetido en todos los pasos.
    """
    url = "https://api.open-meteo.com/v1/forecast"

    parametros = {
        "latitude": lat,
        "longitude": lon,
        "forecast_hours": horas,
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "vapour_pressure_deficit",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "precipitation",
            "shortwave_radiation",
            "soil_moisture_0_to_7cm",
        ],
    }

    respuesta = requests.get(url, params=parametros, timeout=10)
    respuesta.raise_for_status()
    datos = respuesta.json()["hourly"]

    n = len(datos["temperature_2m"])
    serie = []
    for i in range(n):
        serie.append({
            "temperatura": datos["temperature_2m"][i],
            "humedad_relativa": datos["relative_humidity_2m"][i],
            "vpd": datos["vapour_pressure_deficit"][i],
            "viento_velocidad": (datos["wind_speed_10m"][i] or 0) / 3.6,
            "viento_rafagas": (datos["wind_gusts_10m"][i] or 0) / 3.6,
            "viento_direccion": datos["wind_direction_10m"][i],
            "precipitacion": datos["precipitation"][i],
            "radiacion_solar": datos["shortwave_radiation"][i],
            "humedad_suelo": datos["soil_moisture_0_to_7cm"][i],
        })
    return serie


def obtener_elevacion_grid(lat_centro: float, lon_centro: float, radio_m: float,
                            resolucion: int = 10) -> np.ndarray:
    """
    Obtiene un modelo de elevación de baja resolución (resolucion x
    resolucion puntos) cubriendo un cuadrado de lado 2*radio_m alrededor
    de (lat_centro, lon_centro), usando la API de elevación de Open-Meteo
    en una sola consulta por lotes.

    Se usa una malla gruesa (por defecto 10x10 = 100 puntos: el límite
    real de la API de elevación de Open-Meteo es 100 coordenadas por
    consulta, así que 11x11 = 121 puntos -usado antes- fallaba con 400
    en el 100% de los casos) para no disparar cientos de puntos por
    request; luego se interpola a la
    resolución fina de la grilla de simulación (ver simulador_automata).

    Devuelve un array 2D de elevaciones en metros, o None si la consulta
    falla (en ese caso, la simulación simplemente ignora la pendiente).
    """
    grados_lat_por_m = 1.0 / 111_320.0
    grados_lon_por_m = 1.0 / (111_320.0 * np.cos(np.radians(lat_centro)))

    offsets = np.linspace(-radio_m, radio_m, resolucion)
    lats = lat_centro + offsets[:, None] * grados_lat_por_m * np.ones((1, resolucion))
    lons = lon_centro + offsets[None, :] * grados_lon_por_m * np.ones((resolucion, 1))

    lats_flat = lats.ravel()
    lons_flat = lons.ravel()

    url = "https://api.open-meteo.com/v1/elevation"
    parametros = {
        "latitude": ",".join(f"{v:.6f}" for v in lats_flat),
        "longitude": ",".join(f"{v:.6f}" for v in lons_flat),
    }

    try:
        respuesta = requests.get(url, params=parametros, timeout=15)
        respuesta.raise_for_status()
        elevaciones = respuesta.json()["elevation"]
    except (requests.RequestException, ValueError, KeyError):
        return None

    return np.array(elevaciones, dtype=float).reshape(resolucion, resolucion)
