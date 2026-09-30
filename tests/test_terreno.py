import unittest

import numpy as np

from ingesta_geografica import rasterizar_geografia, _metros_a_grados
from simulador_automata import ESTADO_SIN_COMBUSTIBLE


class ViasContinuas(unittest.TestCase):
    def test_una_via_recta_queda_sin_huecos(self):
        lat, lon = 8.0, -73.0
        _, grados_lon_por_m = _metros_a_grados(lat)
        via = [(lat, lon - 90 * grados_lon_por_m), (lat, lon + 90 * grados_lon_por_m)]
        grid, _ = rasterizar_geografia({"vias": [via]}, lat, lon, 21, 21, 10)
        cols = np.nonzero(grid[10] == ESTADO_SIN_COMBUSTIBLE)[0]
        self.assertGreaterEqual(len(cols), 17)
        self.assertEqual(len(cols), cols.max() - cols.min() + 1)


if __name__ == "__main__":
    unittest.main()
