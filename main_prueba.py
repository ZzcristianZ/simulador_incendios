"""
Demo por consola (sin interfaz gráfica) del simulador completo:
geografía real (OpenStreetMap), elevación real y clima horario evolutivo.
El incendio inicia justo en la coordenada de UBICACION.

Requiere conexión a internet (Nominatim, Overpass y Open-Meteo).
Ajusta UBICACION por la dirección o lugar que quieras evaluar.
"""

from ingesta_clima import obtener_coordenadas
from entorno_simulacion import preparar_terreno, preparar_serie_climatica, clima_en_paso
from simulador_automata import SimuladorIncendio
from metricas_fuego import CalculadorMetricas

UBICACION = "Ocaña, Colombia"
RADIO_M = 300
TAM_CELDA_M = 10
PASOS = 12
FACTOR_ESCENARIO = 3.0  # >1.0 = escenario deliberadamente más severo que el clima medido

print(f"--- Ubicando '{UBICACION}' ---")
lat, lon = obtener_coordenadas(UBICACION)
print(f"Coordenadas: {lat:.5f}, {lon:.5f}")

print("--- Obteniendo geografía real (edificios, agua, bosque, vías) ---")
entorno = preparar_terreno(lat, lon, RADIO_M, TAM_CELDA_M, incluir_pendiente=True)
print(f"Grilla {entorno['filas']}x{entorno['columnas']} celdas | geografía real: {entorno['geografia_real']} "
      f"| pendiente disponible: {entorno['elevacion'] is not None}")

print("--- Obteniendo clima (pronóstico horario si está disponible) ---")
serie_clima, alertas, evolutivo = preparar_serie_climatica(lat, lon, PASOS)
print(f"Clima evolutivo: {evolutivo}")
if alertas:
    print("Variables climáticas de respaldo:")
    for alerta in alertas:
        print(" ", alerta)

sim = SimuladorIncendio(
    filas=entorno["filas"], columnas=entorno["columnas"], tam_celda_m=TAM_CELDA_M,
    grid_inicial=entorno["grid"], elevacion=entorno["elevacion"],
)
fila_origen, col_origen = entorno["celda_origen"]
grid_inicial = sim.grid.copy()
sim.iniciar_incendio(fila_origen, col_origen)

metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=15)

print("\n--- INICIANDO SIMULACIÓN: incendio iniciando justo en tu ubicación ---")
for paso in range(1, PASOS + 1):
    clima_paso = clima_en_paso(serie_clima, paso)
    sim.simular_paso(clima_paso, multiplicador_riesgo=FACTOR_ESCENARIO)
    reporte = metricas.generar_reporte(grid_inicial, sim.grid, paso)

    print(f"\n[Paso {paso} - {reporte['tiempo_minutos']} min]")
    print(f" - Área afectada: {reporte['area_m2']} m² ({reporte['area_hectareas']} ha)")
    print(f" - Focos activos en llamas: {reporte['celdas_activas']}")
    print(f" - Edificios afectados: {reporte['edificios_afectados']} / {reporte['edificios_totales']}")
    print(f" - Velocidad de avance estimada: {reporte['velocidad_m_min']} m/min")

print("\n--- FIN DE LA SIMULACIÓN ---")
