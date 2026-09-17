"""
Índice Fosberg (FFWI) y contenido de humedad de equilibrio (EMC).

Responsabilidad ÚNICA de este módulo: métricas climáticas de peligro de
incendio que se muestran en el tablero con fines informativos.

La física de propagación real (velocidad de avance por dirección) vive en
`modelo_rothermel.py`, que reusa `contenido_humedad_equilibrio` de aquí
como humedad de combustible muerto -- así el EMC se calcula en un solo
lugar y no se duplica ni se cuenta dos veces entre el FFWI (informativo)
y el motor de propagación (Rothermel).
"""

import numpy as np


def contenido_humedad_equilibrio(temp_c: float, hum_rel: float) -> float:
    """
    Contenido de humedad de equilibrio (EMC, %) de un combustible muerto
    fino, aproximación por tramos estándar (Simard 1968 / Fosberg 1978).

    Requiere temperatura en °F, por lo que se convierte aquí desde °C.
    """
    temp_f = temp_c * 9.0 / 5.0 + 32.0
    hum_rel = float(np.clip(hum_rel, 0, 100))

    if hum_rel < 10:
        m = 0.03229 + 0.281073 * hum_rel - 0.000578 * hum_rel * temp_f
    elif hum_rel < 50:
        m = 2.22749 + 0.160107 * hum_rel - 0.01478 * temp_f
    else:
        m = 21.0606 + 0.005565 * (hum_rel ** 2) - 0.00035 * hum_rel * temp_f - 0.483199 * hum_rel

    return max(m, 0.0)


def calcular_ffwi(clima: dict) -> dict:
    """
    Índice de Peligro de Incendio de Fosberg (Fosberg Fire Weather Index,
    Fosberg 1978). Se calcula SOLO con fines informativos para el
    tablero (no alimenta el motor de propagación).

    Requiere viento en mph, por lo que se convierte aquí desde m/s.

    Devuelve un dict con el valor (0-100 aprox.) y una categoría textual.
    """
    temp_c = clima.get("temperatura", 25.0)
    hum_rel = clima.get("humedad_relativa", 50.0)
    viento_mph = clima.get("viento_velocidad", 3.0) * 2.23694

    m = contenido_humedad_equilibrio(temp_c, hum_rel)
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
