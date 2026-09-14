import numpy as np

def calcular_probabilidad_ignicion(clima, dx, dy):
    # Lectura defensiva de parámetros meteorológicos
    temp = clima.get("temperatura", 25.0)
    hum_rel = clima.get("humedad_relativa", 50.0)
    viento_vel = clima.get("viento_velocidad", 3.0)
    hum_suelo = clima.get("humedad_suelo", 0.30)
    
    if hum_suelo is None:
        hum_suelo = 0.30

    # Factor suelo
    f_suelo = max(0.2, 1.0 - (hum_suelo / 0.5))
    
    
    # 1. Probabilidad base del combustible forestal
    p_base = 0.12
    
    # 2. Factor Temperatura (°C): A mayor temperatura, mayor facilidad de ignición
    # Referencia estándar de 20°C
    f_temp = 1.0 + 0.03 * max(0, clima["temperatura"] - 20.0)
    
    # 3. Factor Humedad Relativa (%): A mayor humedad, actúa como retardante natural
    # Si la humedad es 90% (como en tu prueba), f_hum reduce drásticamente el riesgo
    f_hum = max(0.05, 1.0 - (clima["humedad_relativa"] / 100.0))
    
    # 4. Factor Déficit de Presión de Vapor - VPD (kPa): Mide la capacidad del aire de resecar el combustible
    # Un VPD alto (> 1.5 kPa) vuelve la vegetación altamente inflamable
    f_vpd = 1.0 + 0.3 * max(0.0, clima["vpd"])
    
    # 5. Factor de Humedad del Suelo (m³/m³): Suelo húmedo frena la propagación subterránea/de superficie baja
    humedad_actual = clima.get("humedad_suelo")
    humedad_segura = humedad_actual if humedad_actual is not None else 0.3 # 0.3 como valor por defecto
    f_suelo = max(0.2, 1.0 - (humedad_segura / 0.5))    
    # 6. Factor de Radiación Solar (W/m²): Precalentamiento diurno de la superficie
    f_rad = 1.0 + (clima["radiacion_solar"] / 1000.0) * 0.1
    
    # 7. Factor de Precipitación (mm): Si llueve o llovió recientemente (> 0), anula casi por completo el fuego
    if clima["precipitacion"] > 0.0:
        return 0.0  # El fuego se extingue o no puede avanzar
        
    # 8. Factor Viento (Velocidad, Ráfagas y Dirección): 
    # Calcula el ángulo entre la dirección del viento y la celda vecina (dx, dy)
    angulo_celda_rad = np.arctan2(dy, dx)
    angulo_celda_deg = np.degrees(angulo_celda_rad) % 360
    
    # Diferencia angular entre hacia dónde apunta el viento y la celda evaluada
    diferencia_angulo = np.radians(clima["viento_direccion"] - angulo_celda_deg)
    
    # Velocidad efectiva incluyendo el impacto estocástico de las ráfagas
    velocidad_efectiva = clima["viento_velocidad"] + 0.2 * (clima["viento_rafagas"] - clima["viento_velocidad"])
    
    # El viento acelera exponencialmente la propagación si sopla en dirección a la celda vecina
    f_viento = np.exp(0.18 * velocidad_efectiva * np.cos(diferencia_angulo))

    # Combinación acoplada de todos los factores
    p_final = p_base * f_temp * f_hum * f_vpd * f_suelo * f_rad * f_viento
    
    # Restringir el valor final estricto entre 0.0 y 1.0 (probabilidad porcentual)
    return float(np.clip(p_final, 0.0, 1.0))




