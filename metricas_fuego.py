import numpy as np
from scipy import ndimage

from simulador_automata import ESTADO_QUEMADO, ESTADO_FUEGO, ESTADO_URBANO


class CalculadorMetricas:
    def __init__(self, tam_celda_m: int = 10, minutos_por_paso: int = 15, origen=None):
        """origen: (fila, col) del punto de ignición, para medir la
        velocidad de cabeza. Sin origen se reporta la velocidad radial
        equivalente (radio del círculo de igual área / tiempo)."""
        self.tam_celda_m = tam_celda_m
        self.area_celda_m2 = tam_celda_m ** 2
        self.minutos_por_paso = minutos_por_paso
        self.origen = origen
        self._etiquetas_edificios = None
        self._num_edificios_totales = 0

    def _preparar_edificios(self, grid_inicial):
        """
        Agrupa las celdas urbanas contiguas en 'edificios' individuales
        (componentes conexas) la primera vez que se necesita, para poder
        reportar cuántas estructuras distintas fueron afectadas en vez de
        solo el % de celdas urbanas quemadas.
        """
        if self._etiquetas_edificios is None:
            mascara_urbana = grid_inicial == ESTADO_URBANO
            self._etiquetas_edificios, self._num_edificios_totales = ndimage.label(mascara_urbana)

    def generar_reporte(self, grid_inicial, grid_actual, paso_actual: int) -> dict:
        self._preparar_edificios(grid_inicial)

        celdas_quemadas = np.sum(grid_actual == ESTADO_QUEMADO)
        celdas_en_llamas = np.sum(grid_actual == ESTADO_FUEGO)
        celdas_afectadas_total = celdas_quemadas + celdas_en_llamas

        area_afectada_m2 = celdas_afectadas_total * self.area_celda_m2
        area_hectareas = area_afectada_m2 / 10000.0

        tiempo_transcurrido_min = paso_actual * self.minutos_por_paso

        # Daño estructural a nivel de EDIFICIO individual (no de celda).
        mascara_afectada = (grid_actual == ESTADO_QUEMADO) | (grid_actual == ESTADO_FUEGO)
        if self._num_edificios_totales > 0:
            etiquetas_afectadas = self._etiquetas_edificios[mascara_afectada & (self._etiquetas_edificios > 0)]
            edificios_afectados = len(np.unique(etiquetas_afectadas))
        else:
            edificios_afectados = 0

        urbanas_iniciales = np.sum(grid_inicial == ESTADO_URBANO)
        urbanas_afectadas_celdas = np.sum((grid_inicial == ESTADO_URBANO) & mascara_afectada)
        porcentaje_urbano_afectado = (
            (urbanas_afectadas_celdas / urbanas_iniciales * 100) if urbanas_iniciales > 0 else 0
        )

        # Velocidad de cabeza: distancia del origen a la celda afectada más
        # lejana, sobre el tiempo transcurrido. (sqrt(área)/tiempo, lo que se
        # usaba antes, no es una velocidad: en un círculo infla el radio 1.77x.)
        if tiempo_transcurrido_min <= 0 or celdas_afectadas_total == 0:
            velocidad_avance = 0.0
        elif self.origen is not None:
            filas_af, cols_af = np.nonzero(mascara_afectada)
            distancia_m = np.hypot(filas_af - self.origen[0], cols_af - self.origen[1]).max() * self.tam_celda_m
            velocidad_avance = distancia_m / tiempo_transcurrido_min
        else:
            velocidad_avance = np.sqrt(area_afectada_m2 / np.pi) / tiempo_transcurrido_min

        return {
            "tiempo_minutos": tiempo_transcurrido_min,
            "area_m2": area_afectada_m2,
            "area_hectareas": round(area_hectareas, 3),
            "celdas_activas": int(celdas_en_llamas),
            "edificios_totales": int(self._num_edificios_totales),
            "edificios_afectados": int(edificios_afectados),
            "porcentaje_urbano_afectado": round(porcentaje_urbano_afectado, 2),
            "velocidad_m_min": round(velocidad_avance, 2),
        }
