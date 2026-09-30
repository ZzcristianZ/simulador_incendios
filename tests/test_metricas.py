import unittest

import numpy as np

from metricas_fuego import CalculadorMetricas
from simulador_automata import ESTADO_VEGETACION_LIGERA, ESTADO_QUEMADO, ESTADO_FUEGO


class VelocidadDePropagacion(unittest.TestCase):
    def setUp(self):
        self.inicial = np.full((21, 21), ESTADO_VEGETACION_LIGERA, dtype=int)
        self.actual = self.inicial.copy()
        self.actual[10, 10:21] = ESTADO_QUEMADO  # el frente avanzó 10 celdas al este
        self.actual[10, 20] = ESTADO_FUEGO

    def test_con_origen_mide_la_distancia_de_cabeza(self):
        rep = CalculadorMetricas(10, 15, origen=(10, 10)).generar_reporte(self.inicial, self.actual, 1)
        self.assertAlmostEqual(rep["velocidad_m_min"], 100.0 / 15, places=2)

    def test_sin_origen_usa_el_radio_equivalente(self):
        rep = CalculadorMetricas(10, 15).generar_reporte(self.inicial, self.actual, 1)
        self.assertAlmostEqual(rep["velocidad_m_min"], np.sqrt(11 * 100.0 / np.pi) / 15, places=2)

    def test_en_el_paso_cero_la_velocidad_es_cero(self):
        rep = CalculadorMetricas(10, 15, origen=(10, 10)).generar_reporte(self.inicial, self.actual, 0)
        self.assertEqual(rep["velocidad_m_min"], 0.0)


class VelocidadCongeladaAlTocarElBorde(unittest.TestCase):
    """Reproduce el bug: sin congelar, la velocidad de cabeza sigue cayendo
    después de tocar el borde porque la distancia queda acotada por la
    grilla mientras el tiempo sigue creciendo."""

    def setUp(self):
        self.calc = CalculadorMetricas(10, 15, origen=(10, 10))
        self.inicial = np.full((21, 21), ESTADO_VEGETACION_LIGERA, dtype=int)

    def _grid(self, hasta_col):
        grid = self.inicial.copy()
        grid[10, 10:hasta_col + 1] = ESTADO_QUEMADO
        grid[10, hasta_col] = ESTADO_FUEGO
        return grid

    def test_la_velocidad_no_sigue_bajando_tras_tocar_el_borde(self):
        # Paso 1: el frente llega a la columna 12, lejos del borde (col 20).
        paso1 = self._grid(12)
        rep1 = self.calc.generar_reporte(self.inicial, paso1, 1)
        self.assertFalse(rep1["toca_borde"])

        # Paso 2: el frente llega exactamente a la columna 20 -> toca el borde.
        # Esta medición sigue siendo válida (el frente apenas llega ahí).
        paso2 = self._grid(20)
        rep2 = self.calc.generar_reporte(self.inicial, paso2, 2)
        self.assertTrue(rep2["toca_borde"])
        self.assertAlmostEqual(rep2["velocidad_m_min"], 100.0 / 30, places=2)

        # Paso 3: el frente "sigue" en el borde (la grilla no puede mostrar
        # más), pero el tiempo avanzó. Sin el fix, la velocidad recalculada
        # sería 100/45 (menor); con el fix se mantiene la del paso 2.
        rep3 = self.calc.generar_reporte(self.inicial, paso2, 3)
        self.assertTrue(rep3["toca_borde"])
        self.assertEqual(rep3["velocidad_m_min"], rep2["velocidad_m_min"])
        self.assertNotAlmostEqual(rep3["velocidad_m_min"], 100.0 / 45, places=2)


if __name__ == "__main__":
    unittest.main()
