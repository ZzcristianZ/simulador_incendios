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


class ElipseEfectiva(unittest.TestCase):
    """Viento y pendiente combinados como vectores (Finney 1998)."""

    def setUp(self):
        self.calma = R.velocidad_base(R.FUEL_MODEL_DENSO, clima(30, 35))
        self.viento = R.velocidad_base(R.FUEL_MODEL_DENSO, clima(30, 35, 6.0))
        self.subida = (np.array([0.3]), np.array([90.0]))  # 30 % cuesta arriba hacia el este

    def test_la_cabeza_es_mucho_mas_rapida_que_la_cola(self):
        cabeza, cola, _, azimut = R.elipse_efectiva(self.viento, 90.0, np.zeros(1), np.zeros(1))
        self.assertAlmostEqual(cabeza[0], self.viento.r0_m_min * (1 + self.viento.phi_viento), places=6)
        self.assertGreater(cabeza[0], 5 * cola[0])
        self.assertAlmostEqual(azimut[0], 90.0)

    def test_sin_pendiente_el_viento_efectivo_reproduce_anderson(self):
        _, _, lwr, _ = R.elipse_efectiva(self.viento, 90.0, np.zeros(1), np.zeros(1))
        self.assertAlmostEqual(lwr[0], R.razon_largo_ancho(R.FUEL_MODEL_DENSO, clima(30, 35, 6.0)), places=9)

    def test_cuesta_arriba_acelera(self):
        cabeza, _, _, azimut = R.elipse_efectiva(self.calma, 0.0, *self.subida)
        self.assertAlmostEqual(cabeza[0], 0.6764, places=3)
        self.assertAlmostEqual(azimut[0], 90.0)

    def test_cuesta_abajo_retrocede_mas_lento_que_en_llano(self):
        _, cola, _, _ = R.elipse_efectiva(self.calma, 0.0, *self.subida)
        self.assertLess(cola[0], self.calma.r0_m_min)

    def test_viento_y_pendiente_alineados_se_suman(self):
        phi_s = R.elipse_efectiva(self.calma, 0.0, *self.subida)[0][0] / self.calma.r0_m_min - 1.0
        cabeza, _, _, _ = R.elipse_efectiva(self.viento, 90.0, *self.subida)
        self.assertAlmostEqual(cabeza[0], self.viento.r0_m_min * (1 + self.viento.phi_viento + phi_s), places=6)

    def test_viento_y_pendiente_opuestos_se_restan(self):
        solo_viento, _, _, _ = R.elipse_efectiva(self.viento, 90.0, np.zeros(1), np.zeros(1))
        opuestos, _, _, azimut = R.elipse_efectiva(self.viento, 90.0, np.array([0.3]), np.array([270.0]))
        self.assertLess(opuestos[0], solo_viento[0])
        self.assertAlmostEqual(azimut[0], 90.0)  # domina el viento: phi_w 4.0 > phi_s 1.6

    def test_combustible_que_no_arde_da_velocidad_cero(self):
        base = R.velocidad_base(R.FUEL_MODEL_LIGERO, clima(20, 75))
        cabeza, cola, lwr, _ = R.elipse_efectiva(base, 90.0, np.zeros(2), np.zeros(2))
        np.testing.assert_array_equal(cabeza, 0.0)
        np.testing.assert_array_equal(cola, 0.0)
        np.testing.assert_array_equal(lwr, 1.0)


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
