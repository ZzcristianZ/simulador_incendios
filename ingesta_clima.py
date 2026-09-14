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



