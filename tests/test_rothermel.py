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


class HumedadDeCombustible(unittest.TestCase):
    def setUp(self):
        self.c = clima(30, 35)
        self.emc = contenido_humedad_equilibrio(30, 35)

    def test_sin_humedades_explicitas_usa_la_emc(self):
        implicito = R.velocidad_base(R.FUEL_MODEL_DENSO, self.c).r0_m_min
        explicito = R.velocidad_base(R.FUEL_MODEL_DENSO, self.c, (self.emc, self.emc, self.emc)).r0_m_min
        self.assertAlmostEqual(implicito, explicito, places=9)

    def test_combustible_grueso_humedo_frena_el_bosque(self):
        seco = R.velocidad_base(R.FUEL_MODEL_DENSO, self.c, (self.emc, self.emc, self.emc)).r0_m_min
        humedo = R.velocidad_base(R.FUEL_MODEL_DENSO, self.c, (self.emc, 20.0, 20.0)).r0_m_min
        self.assertLess(humedo, seco)

    def test_el_pasto_solo_depende_de_la_clase_1h(self):
        a = R.velocidad_base(R.FUEL_MODEL_LIGERO, self.c, (self.emc, self.emc, self.emc)).r0_m_min
        b = R.velocidad_base(R.FUEL_MODEL_LIGERO, self.c, (self.emc, 30.0, 30.0)).r0_m_min
        self.assertAlmostEqual(a, b, places=9)

    def test_combustible_vivo_mas_seco_propaga_mas_rapido(self):
        normal = R.velocidad_base(R.FUEL_MODEL_DENSO, self.c).r0_m_min
        seco = R.velocidad_base(R.FUEL_MODEL_DENSO, dict(self.c, humedad_combustible_vivo=60.0)).r0_m_min
        self.assertGreater(seco, normal)


if __name__ == "__main__":
    unittest.main()
