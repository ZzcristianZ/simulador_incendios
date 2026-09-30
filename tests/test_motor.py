import unittest

import numpy as np

import modelo_rothermel as R
from modelo_probabilidad import contenido_humedad_equilibrio
from simulador_automata import (
    SimuladorIncendio, ESTADO_VEGETACION_DENSA, ESTADO_VEGETACION_LIGERA,
    ESTADO_AGUA, ESTADO_SIN_COMBUSTIBLE, ESTADO_FUEGO, ESTADO_QUEMADO,
)

SECO = {"temperatura": 30.0, "humedad_relativa": 35.0, "viento_velocidad": 0.0,
        "viento_direccion": 0.0, "precipitacion": 0.0}
MIN_PASO = 15


def correr(clima, pasos, lado=121, tam=2.0, origen=None, grid=None, elevacion=None,
           multiplicador=1.0, **kw):
    if grid is None:
        grid = np.full((lado, lado), ESTADO_VEGETACION_DENSA, dtype=int)
    sim = SimuladorIncendio(grid.shape[0], grid.shape[1], tam, grid_inicial=grid, elevacion=elevacion, **kw)
    f, c = origen or (grid.shape[0] // 2, grid.shape[1] // 2)
    sim.iniciar_incendio(f, c)
    for _ in range(pasos):
        sim.simular_paso(clima, multiplicador)
    return sim, (f, c)


def afectadas(sim):
    return np.isin(sim.grid, (ESTADO_FUEGO, ESTADO_QUEMADO))


def extension(sim, fila, col):
    """(hacia el este, hacia el oeste) en celdas, sobre la fila del origen."""
    cols = np.nonzero(afectadas(sim)[fila])[0]
    return cols.max() - col, col - cols.min()


class GeometriaDelFrente(unittest.TestCase):
    def test_sin_viento_el_radio_crece_a_la_velocidad_de_rothermel(self):
        r0 = R.velocidad_base(R.FUEL_MODEL_DENSO, SECO).r0_m_min
        sim, (f, c) = correr(SECO, pasos=16, lado=141)
        esperado = r0 * 16 * MIN_PASO
        este, oeste = extension(sim, f, c)
        self.assertAlmostEqual(este * 2.0, esperado, delta=0.05 * esperado + 2.0)
        self.assertAlmostEqual(oeste * 2.0, esperado, delta=0.05 * esperado + 2.0)
        circulo = np.pi * esperado ** 2
        self.assertAlmostEqual(afectadas(sim).sum() * 4.0, circulo, delta=0.08 * circulo)

    def test_viento_del_oeste_empuja_el_fuego_al_este(self):
        clima = dict(SECO, viento_velocidad=6.0, viento_direccion=270.0)
        sim, (f, c) = correr(clima, pasos=4)
        este, oeste = extension(sim, f, c)
        self.assertGreater(este, 3 * oeste)

    def test_con_viento_el_frente_es_la_elipse_de_anderson(self):
        clima = dict(SECO, viento_velocidad=6.0, viento_direccion=270.0)
        base = R.velocidad_base(R.FUEL_MODEL_DENSO, clima)
        lwr = R.razon_largo_ancho(R.FUEL_MODEL_DENSO, clima)
        e = np.sqrt(1 - 1 / lwr ** 2)
        cabeza = base.r0_m_min * (1 + base.phi_viento)
        cola = cabeza * (1 - e) / (1 + e)
        t = 8 * MIN_PASO
        grid = np.full((161, 201), ESTADO_VEGETACION_DENSA, dtype=int)
        sim, (f, c) = correr(clima, pasos=8, grid=grid, origen=(80, 30))
        este, oeste = extension(sim, f, c)
        self.assertAlmostEqual(este * 2.0, cabeza * t, delta=0.05 * cabeza * t + 2.0)
        self.assertAlmostEqual(oeste * 2.0, cola * t, delta=0.05 * cola * t + 2.0)
        semieje = (cabeza + cola) * t / 2
        elipse = np.pi * semieje * (semieje / lwr)
        self.assertAlmostEqual(afectadas(sim).sum() * 4.0, elipse, delta=0.08 * elipse)

    def test_la_direccion_360_equivale_a_0(self):
        a, _ = correr(dict(SECO, viento_velocidad=4.0, viento_direccion=0.0), pasos=2, lado=61)
        b, _ = correr(dict(SECO, viento_velocidad=4.0, viento_direccion=360.0), pasos=2, lado=61)
        np.testing.assert_allclose(a.llegada, b.llegada)

    def test_cuesta_arriba_acelera_y_cuesta_abajo_retrocede(self):
        lado = 141
        _, col_i = np.mgrid[0:lado, 0:lado]
        elevacion = 0.3 * col_i * 2.0  # sube 30 % hacia el este
        sim, (f, c) = correr(SECO, pasos=8, lado=lado, elevacion=elevacion)
        base = R.velocidad_base(R.FUEL_MODEL_DENSO, SECO)
        arriba, abajo, _, _ = R.elipse_efectiva(base, 0.0, np.array([0.3]), np.array([90.0]))
        t = 8 * MIN_PASO
        este, oeste = extension(sim, f, c)
        self.assertAlmostEqual(este * 2.0, arriba[0] * t, delta=0.05 * arriba[0] * t + 2.0)
        self.assertAlmostEqual(oeste * 2.0, abajo[0] * t, delta=0.05 * abajo[0] * t + 2.0)

    def test_en_pasto_con_viento_fuerte_el_area_es_la_elipse(self):
        clima = dict(SECO, viento_velocidad=6.0, viento_direccion=270.0)  # LWR 3.5
        base = R.velocidad_base(R.FUEL_MODEL_LIGERO, clima)
        lwr = R.razon_largo_ancho(R.FUEL_MODEL_LIGERO, clima)
        e = np.sqrt(1 - 1 / lwr ** 2)
        cabeza = base.r0_m_min * (1 + base.phi_viento)
        cola = cabeza * (1 - e) / (1 + e)
        semieje = (cabeza + cola) * MIN_PASO / 2
        elipse = np.pi * semieje * (semieje / lwr)
        grid = np.full((101, 161), ESTADO_VEGETACION_LIGERA, dtype=int)
        sim, (f, c) = correr(clima, pasos=1, grid=grid, tam=5.0, origen=(50, 20))
        este, _ = extension(sim, f, c)
        self.assertAlmostEqual(este * 5.0, cabeza * MIN_PASO, delta=0.05 * cabeza * MIN_PASO + 5.0)
        self.assertAlmostEqual(afectadas(sim).sum() * 25.0, elipse, delta=0.08 * elipse)

    def test_informa_la_elongacion_maxima(self):
        clima = dict(SECO, viento_velocidad=10.0, viento_direccion=270.0)
        grid = np.full((21, 21), ESTADO_VEGETACION_LIGERA, dtype=int)
        sim, _ = correr(clima, pasos=1, grid=grid, tam=10.0)
        self.assertAlmostEqual(sim.lwr_max, 8.0)

    def test_en_pasto_el_viento_aumenta_el_area(self):
        # El caso que antes fallaba: la probabilidad se saturaba en 1 y el
        # viento no cambiaba nada.
        grid = np.full((121, 161), ESTADO_VEGETACION_LIGERA, dtype=int)
        areas = []
        for v in (0.0, 3.0, 6.0):
            clima = dict(SECO, viento_velocidad=v, viento_direccion=270.0)
            sim, _ = correr(clima, pasos=1, grid=grid, tam=10.0, origen=(60, 20))
            areas.append(afectadas(sim).sum())
        self.assertLess(areas[0], areas[1])
        self.assertLess(areas[1], areas[2])

    def test_el_factor_de_escenario_escala_los_tiempos(self):
        normal, (f, c) = correr(SECO, pasos=8, lado=61)
        doble, _ = correr(SECO, pasos=8, lado=61, multiplicador=2.0)
        self.assertAlmostEqual(doble.llegada[f, c + 10] * 2, normal.llegada[f, c + 10],
                               delta=0.03 * normal.llegada[f, c + 10])


class Cortafuegos(unittest.TestCase):
    def test_una_columna_de_agua_detiene_el_fuego(self):
        grid = np.full((61, 61), ESTADO_VEGETACION_DENSA, dtype=int)
        grid[:, 40] = ESTADO_AGUA
        clima = dict(SECO, viento_velocidad=6.0, viento_direccion=270.0)
        sim, _ = correr(clima, pasos=16, grid=grid)
        self.assertTrue(afectadas(sim)[:, 39].any())
        self.assertFalse(afectadas(sim)[:, 41:].any())

    def test_una_via_diagonal_no_se_cruza(self):
        grid = np.full((61, 61), ESTADO_VEGETACION_DENSA, dtype=int)
        for i in range(61):
            grid[i, i] = ESTADO_SIN_COMBUSTIBLE
        sim, _ = correr(SECO, pasos=40, grid=grid, origen=(40, 10))
        filas, cols = np.nonzero(afectadas(sim))
        self.assertGreater(len(filas), 100)
        self.assertTrue(np.all(filas > cols))


class ClimaQueDetiene(unittest.TestCase):
    def test_la_lluvia_pausa_el_avance(self):
        sim, _ = correr(SECO, pasos=4, lado=61)
        antes = afectadas(sim).sum()
        sim.simular_paso(dict(SECO, precipitacion=2.0))
        self.assertEqual(afectadas(sim).sum(), antes)
        sim.simular_paso(SECO)
        self.assertGreater(afectadas(sim).sum(), antes)

    def test_combustible_demasiado_humedo_no_propaga(self):
        humedo = dict(SECO, temperatura=20.0, humedad_relativa=75.0)
        grid = np.full((31, 31), ESTADO_VEGETACION_LIGERA, dtype=int)
        sim, _ = correr(humedo, pasos=4, grid=grid)
        self.assertEqual(afectadas(sim).sum(), 1)


class CasosLimite(unittest.TestCase):
    def test_origen_en_agua_no_propaga_ni_se_cuelga(self):
        grid = np.full((21, 21), ESTADO_AGUA, dtype=int)
        sim, _ = correr(SECO, pasos=4, grid=grid)
        self.assertLessEqual(afectadas(sim).sum(), 1)

    def test_el_frente_gira_si_el_viento_cambia(self):
        oeste = dict(SECO, viento_velocidad=6.0, viento_direccion=270.0)  # empuja al este
        sur = dict(SECO, viento_velocidad=6.0, viento_direccion=180.0)    # empuja al norte
        grid = np.full((121, 121), ESTADO_VEGETACION_DENSA, dtype=int)
        sim = SimuladorIncendio(121, 121, 2.0, grid_inicial=grid)
        sim.iniciar_incendio(60, 60)
        for clima in [oeste] * 4 + [sur] * 4:
            sim.simular_paso(clima)
        filas, cols = np.nonzero(afectadas(sim))
        self.assertGreater(cols.max() - 60, 60 - cols.min())    # avanzó al este
        self.assertGreater(60 - filas.min(), filas.max() - 60)  # y luego al norte

    def test_terreno_irregular_no_produce_nan(self):
        rng = np.random.default_rng(0)
        elevacion = np.cumsum(np.cumsum(rng.normal(0, 1, (61, 61)), axis=0), axis=1)
        sim, _ = correr(SECO, pasos=4, lado=61, elevacion=elevacion)
        self.assertFalse(np.isnan(sim.llegada).any())
        self.assertGreater(afectadas(sim).sum(), 1)


class Heterogeneidad(unittest.TestCase):
    def test_misma_semilla_mismo_resultado(self):
        a, _ = correr(SECO, pasos=4, lado=61, heterogeneidad=0.3, semilla=7)
        b, _ = correr(SECO, pasos=4, lado=61, heterogeneidad=0.3, semilla=7)
        c, _ = correr(SECO, pasos=4, lado=61, heterogeneidad=0.3, semilla=8)
        np.testing.assert_array_equal(a.llegada, b.llegada)
        self.assertFalse(np.array_equal(a.llegada, c.llegada))


class HumedadEnElTiempo(unittest.TestCase):
    def test_el_combustible_fino_responde_mas_rapido_que_el_grueso(self):
        humedo = dict(SECO, temperatura=20.0, humedad_relativa=70.0)
        seco = dict(SECO, temperatura=32.0, humedad_relativa=25.0)
        grid = np.full((11, 11), ESTADO_VEGETACION_DENSA, dtype=int)
        sim = SimuladorIncendio(11, 11, 10.0, grid_inicial=grid)
        sim.simular_paso(humedo)
        for _ in range(4):  # una hora de clima seco
            sim.simular_paso(seco)
        m1, m10, m100 = sim.humedad_muerta
        emc_h = contenido_humedad_equilibrio(20, 70)
        emc_s = contenido_humedad_equilibrio(32, 25)
        self.assertAlmostEqual(m1, emc_s + (emc_h - emc_s) * np.exp(-1.0), places=6)
        self.assertGreater(m10, m1)
        self.assertGreater(m100, m10)


if __name__ == "__main__":
    unittest.main()
