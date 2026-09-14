import numpy as np

class CalculadorMetricas:
    def __init__(self, tam_celda_m: int = 10, minutos_por_paso: int = 15):
        self.tam_celda_m = tam_celda_m
        self.area_celda_m2 = tam_celda_m ** 2  # 10m x 10m = 100 m²
        self.minutos_por_paso = minutos_por_paso

    def generar_reporte(self, grid_inicial, grid_actual, paso_actual: int):
        celdas_quemadas = np.sum(grid_actual == 0)
        celdas_en_llamas = np.sum(grid_actual == 2)
        celdas_afectadas_total = celdas_quemadas + celdas_en_llamas
        
        area_afectada_m2 = celdas_afectadas_total * self.area_celda_m2
        area_hectareas = area_afectada_m2 / 10000.0
        
        tiempo_transcurrido_min = paso_actual * self.minutos_por_paso
        
        # Evaluación de impacto en la zona urbana (Estado 3)
        urbanas_iniciales = np.sum(grid_inicial == 3)
        urbanas_destruidas = np.sum((grid_inicial == 3) & ((grid_actual == 0) | (grid_actual == 2)))
        porcentaje_urbano_danado = (urbanas_destruidas / urbanas_iniciales * 100) if urbanas_iniciales > 0 else 0
        
        # Velocidad media de expansión lineal (m/min)
        velocidad_avance = (np.sqrt(area_afectada_m2) / tiempo_transcurrido_min) if tiempo_transcurrido_min > 0 else 0

        return {
            "tiempo_minutos": tiempo_transcurrido_min,
            "area_m2": area_afectada_m2,
            "area_hectareas": round(area_hectareas, 3),
            "celdas_activas": celdas_en_llamas,
            "estructuras_danadas": urbanas_destruidas,
            "porcentaje_urbano_afectado": round(porcentaje_urbano_danado, 2),
            "velocidad_m_min": round(velocidad_avance, 2)
        }