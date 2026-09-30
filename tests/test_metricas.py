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


if __name__ == "__main__":
    unittest.main()
