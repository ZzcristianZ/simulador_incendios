import unittest

import numpy as np

from ingesta_geografica import rasterizar_geografia, _metros_a_grados
from simulador_automata import ESTADO_SIN_COMBUSTIBLE
from entorno_simulacion import terreno_controlado


class ViasContinuas(unittest.TestCase):
    def test_una_via_recta_queda_sin_huecos(self):
        lat, lon = 8.0, -73.0
        _, grados_lon_por_m = _metros_a_grados(lat)
        via = [(lat, lon - 90 * grados_lon_por_m), (lat, lon + 90 * grados_lon_por_m)]
        grid, _ = rasterizar_geografia({"vias": [via]}, lat, lon, 21, 21, 10)
        cols = np.nonzero(grid[10] == ESTADO_SIN_COMBUSTIBLE)[0]
        self.assertGreaterEqual(len(cols), 17)
        self.assertEqual(len(cols), cols.max() - cols.min() + 1)


class TerrenoControlado(unittest.TestCase):
    def test_plano_que_sube_al_este(self):
        t = terreno_controlado(11, 11, 10.0, pendiente_pct=20.0, azimut_subida=90.0)
        self.assertAlmostEqual(t["elevacion"][5, 6] - t["elevacion"][5, 5], 2.0)
        self.assertAlmostEqual(t["elevacion"][4, 5] - t["elevacion"][5, 5], 0.0)
        self.assertEqual(t["celda_origen"], (5, 5))

    def test_sin_pendiente_no_hay_elevacion(self):
        self.assertIsNone(terreno_controlado(11, 11, 10.0)["elevacion"])


if __name__ == "__main__":
    unittest.main()
