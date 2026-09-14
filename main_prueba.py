from ingesta_clima import obtener_coordenadas, obtener_clima_tiempo_real
from simulador_automata import SimuladorIncendio
from metricas_fuego import CalculadorMetricas
import numpy as np

# 1. Obtenemos datos de la API
lat, lon = obtener_coordenadas("Ocaña, Colombia")
clima = obtener_clima_tiempo_real(lat, lon)

# 2. Inicializamos componentes
sim = SimuladorIncendio(filas=50, columnas=50, tam_celda_m=10)
metricas = CalculadorMetricas(tam_celda_m=10, minutos_por_paso=15)

grid_inicial = sim.grid.copy()
sim.iniciar_incendio(25, 20)

print("--- INICIANDO SIMULACIÓN CON REPORTE ESTADÍSTICO ---")
# Evaluamos 12 pasos (equivalente a 3 horas de incendio)
# Usamos multiplicador_riesgo=15.0 para evaluar un escenario de incendio forestal activo
for paso in range(1, 13):
    sim.simular_paso(clima, multiplicador_riesgo=15.0)
    reporte = metricas.generar_reporte(grid_inicial, sim.grid, paso)
    
    print(f"\n[Paso {paso} - {reporte['tiempo_minutos']} min]")
    print(f" - Área afectada: {reporte['area_m2']} m² ({reporte['area_hectareas']} ha)")
    print(f" - Focos activos en llamas: {reporte['celdas_activas']}")
    print(f" - Estructuras urbanas dañadas: {reporte['estructuras_danadas']} ({reporte['porcentaje_urbano_afectado']}%)")
    print(f" - Velocidad de avance estimada: {reporte['velocidad_m_min']} m/min")