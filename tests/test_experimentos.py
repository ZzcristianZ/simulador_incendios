import unittest

from experimentos import barrido, correr, CLIMA_BASE
from simulador_automata import ESTADO_VEGETACION_DENSA


def ultimo(filas, valor):
    return [f for f in filas if f["valor"] == valor][-1]


class LaboratorioDeSensibilidad(unittest.TestCase):
    def test_mas_viento_mas_velocidad_y_mas_area(self):
        filas = barrido("viento_velocidad", [0.0, 6.0], pasos=4, lado=81)
        calma, viento = ultimo(filas, 0.0), ultimo(filas, 6.0)
        self.assertGreater(viento["velocidad_m_min"], calma["velocidad_m_min"])
        self.assertGreater(viento["area_ha"], calma["area_ha"])

    def test_mas_humedad_menos_area(self):
        filas = barrido("humedad_relativa", [20.0, 65.0], pasos=4, lado=81)
        self.assertGreater(ultimo(filas, 20.0)["area_ha"], ultimo(filas, 65.0)["area_ha"])

    def test_una_fila_por_paso_y_valor(self):
        filas = barrido("pendiente_pct", [0.0, 30.0], pasos=3, lado=41)
        self.assertEqual(len(filas), 6)
        self.assertEqual([f["minuto"] for f in filas[:3]], [15, 30, 45])

    def test_si_no_puede_arder_el_area_es_cero(self):
        humedo = dict(CLIMA_BASE, temperatura=15.0, humedad_relativa=99.0)
        filas = correr(humedo, 0.0, ESTADO_VEGETACION_DENSA, pasos=2, lado=21)
        self.assertEqual([f["area_ha"] for f in filas], [0.0, 0.0])

    def test_marca_cuando_el_fuego_toca_el_borde(self):
        filas = barrido("viento_velocidad", [6.0], pasos=8, lado=21)
        self.assertTrue(filas[-1]["toca_borde"])


if __name__ == "__main__":
    unittest.main()
