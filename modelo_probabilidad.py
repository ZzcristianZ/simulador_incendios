"""
Modelo de probabilidad de ignición.

Responsabilidad ÚNICA de este módulo: dado un estado climático uniforme
sobre la grilla y una dirección de propagación (dx, dy), calcular la
probabilidad "climática" de que el fuego salte de una celda en llamas
a una celda vecina combustible.

Los efectos de PENDIENTE (terreno) y TIPO DE COMBUSTIBLE (pasto, bosque,
urbano) se aplican después, en `simulador_automata.py`, multiplicando
esta probabilidad base. Mantener esto separado evita mezclar física del
clima con las propiedades del terreno/combustible, y evita contar el
mismo efecto dos veces (bug presente en la versión original, donde un
"índice de riesgo" recalculaba temperatura/viento/VPD y volvía a
multiplicar una probabilidad que ya los incluía).

Referencia conceptual: el enfoque de autómata celular con factor
direccional de viento sigue la idea general de Alexandridis et al.
(2008), "A cellular automata model for forest fire spread prediction".
"""

import numpy as np


def calcular_probabilidad_ignicion(clima: dict, dx: int, dy: int) -> float:
    """
    Probabilidad climática de ignición de una celda vecina ubicada en la
    dirección (dx, dy) respecto a la celda en llamas (vecindad de Moore,
    dx, dy en {-1, 0, 1}).

    Combina multiplicativamente: temperatura, humedad relativa, déficit
    de presión de vapor (VPD), humedad del suelo, radiación solar,
    precipitación (corte total si llueve) y viento (velocidad, ráfagas
    y dirección relativa a la celda vecina).
    """
    temperatura = clima.get("temperatura", 25.0)
    humedad_relativa = clima.get("humedad_relativa", 50.0)
    vpd = clima.get("vpd", 1.2)
    radiacion_solar = clima.get("radiacion_solar", 200.0)
    precipitacion = clima.get("precipitacion", 0.0)
    viento_velocidad = clima.get("viento_velocidad", 3.0)
    viento_rafagas = clima.get("viento_rafagas", viento_velocidad)
    viento_direccion = clima.get("viento_direccion", 0.0)

    humedad_suelo = clima.get("humedad_suelo")
    if humedad_suelo is None:
        humedad_suelo = 0.30

    # Si llovió recientemente, no hay ignición posible en esta dirección.
    if precipitacion > 0.0:
        return 0.0

    # 1. Probabilidad base del combustible forestal genérico.
    p_base = 0.12

    # 2. Temperatura (°C): referencia estándar 20°C.
    f_temp = 1.0 + 0.03 * max(0.0, temperatura - 20.0)

    # 3. Humedad relativa (%): actúa como retardante natural.
    f_hum = max(0.05, 1.0 - (humedad_relativa / 100.0))

    # 4. Déficit de presión de vapor (kPa): reseca el combustible.
    f_vpd = 1.0 + 0.3 * max(0.0, vpd)

    # 5. Humedad del suelo (m³/m³): frena la propagación superficial.
    f_suelo = max(0.2, 1.0 - (humedad_suelo / 0.5))

    # 6. Radiación solar (W/m²): precalentamiento diurno.
    f_rad = 1.0 + (radiacion_solar / 1000.0) * 0.1

    # 7. Viento: ángulo entre la dirección del viento y la celda vecina,
    #    con velocidad efectiva que pondera ráfagas.
    angulo_celda_deg = np.degrees(np.arctan2(dy, dx)) % 360
    diferencia_angulo = np.radians(viento_direccion - angulo_celda_deg)
    velocidad_efectiva = viento_velocidad + 0.2 * (viento_rafagas - viento_velocidad)
    f_viento = np.exp(0.18 * velocidad_efectiva * np.cos(diferencia_angulo))

    p_final = p_base * f_temp * f_hum * f_vpd * f_suelo * f_rad * f_viento

    return float(np.clip(p_final, 0.0, 1.0))


def calcular_ffwi(clima: dict) -> dict:
    """
    Índice de Peligro de Incendio de Fosberg (Fosberg Fire Weather Index,
    Fosberg 1978). Se calcula SOLO con fines informativos para el
    tablero (no alimenta el motor de probabilidad, para no duplicar el
    efecto del clima).

    Requiere temperatura en °F y viento en mph, por lo que se convierten
    aquí a partir de las unidades SI usadas en el resto del proyecto.

    Devuelve un dict con el valor (0-100 aprox.) y una categoría textual.
    """
    temp_f = clima.get("temperatura", 25.0) * 9.0 / 5.0 + 32.0
    hum_rel = float(np.clip(clima.get("humedad_relativa", 50.0), 0, 100))
    viento_mph = clima.get("viento_velocidad", 3.0) * 2.23694

    # Contenido de humedad de equilibrio (EMC), aproximación por tramos.
    if hum_rel < 10:
        m = 0.03229 + 0.281073 * hum_rel - 0.000578 * hum_rel * temp_f
    elif hum_rel < 50:
        m = 2.22749 + 0.160107 * hum_rel - 0.01478 * temp_f
    else:
        m = 21.0606 + 0.005565 * (hum_rel ** 2) - 0.00035 * hum_rel * temp_f - 0.483199 * hum_rel

    m = max(m, 0.0)
    eta = 1 - 2 * (m / 30.0) + 1.5 * (m / 30.0) ** 2 - 0.5 * (m / 30.0) ** 3
    eta = max(eta, 0.0)

    ffwi = eta * np.sqrt(1 + viento_mph ** 2) / 0.3002
    ffwi = float(np.clip(ffwi, 0, 150))

    if ffwi < 25:
        categoria = "Bajo"
    elif ffwi < 50:
        categoria = "Moderado"
    elif ffwi < 75:
        categoria = "Alto"
    else:
        categoria = "Extremo"

    return {"valor": round(ffwi, 1), "categoria": categoria}
