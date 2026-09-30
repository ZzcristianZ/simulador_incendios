import unittest

import numpy as np

import modelo_rothermel as R
from modelo_probabilidad import contenido_humedad_equilibrio


def clima(t, hr, v=0.0, direccion=0.0, **extra):
    return {"temperatura": t, "humedad_relativa": hr, "viento_velocidad": v,
            "viento_direccion": direccion, **extra}


class CaracterizacionRothermel(unittest.TestCase):
    """Fija los valores del modelo ya verificado (ver README) para detectar
    cualquier cambio accidental en la física."""

    def test_velocidad_base_pasto(self):
        self.assertAlmostEqual(R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(30, 35)).r0_m_min, 1.3603, places=3)
        self.assertAlmostEqual(R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(22, 65)).r0_m_min, 0.2281, places=3)

    def test_velocidad_base_bosque(self):
        self.assertAlmostEqual(R.velocidad_base(R.FUEL_MODEL_DENSO, clima(30, 35)).r0_m_min, 0.2596, places=3)
        self.assertAlmostEqual(R.velocidad_base(R.FUEL_MODEL_DENSO, clima(22, 65)).r0_m_min, 0.2221, places=3)

    def test_coeficiente_de_viento_y_elipse(self):
        base = R.velocidad_base(R.FUEL_MODEL_DENSO, clima(30, 35, 6.0))
        self.assertAlmostEqual(base.phi_viento, 4.0058, places=3)
        self.assertAlmostEqual(R.razon_largo_ancho(R.FUEL_MODEL_DENSO, clima(30, 35, 6.0)), 1.7711, places=3)
        self.assertAlmostEqual(R.razon_largo_ancho(R.FUEL_MODEL_LIGERO, clima(30, 35, 6.0)), 3.5154, places=3)


class InvariantesFisicos(unittest.TestCase):
    def test_sobre_la_humedad_de_extincion_no_hay_propagacion(self):
        self.assertEqual(R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(20, 75)).r0_m_min, 0.0)

    def test_mas_humedad_menos_velocidad(self):
        seco = R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(30, 35)).r0_m_min
        humedo = R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(25, 50)).r0_m_min
        self.assertGreater(seco, humedo)

    def test_sin_viento_la_elipse_es_un_circulo(self):
        self.assertEqual(R.razon_largo_ancho(R.FUEL_MODEL_DENSO, clima(30, 35, 0.0)), 1.0)


if __name__ == "__main__":
    unittest.main()
