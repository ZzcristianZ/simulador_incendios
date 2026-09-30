"""
Propagación del frente de fuego con el método de conjuntos de nivel
(level set) sobre una grilla de celdas.

El frente es el contorno cero de una función phi (phi <= 0 = quemado) y
avanza en su dirección normal a la velocidad que le da la elipse de
Huygens de cada celda: la elipse de Rothermel (1972) + Anderson (1983)
con viento y pendiente combinados como vectores (Finney 1998). La
velocidad normal es la "función soporte" de esa elipse, así que un
incendio puntual crece exactamente como la elipse, sin el sesgo de los
métodos de vecindad fija (que recortan los flancos: con 8 vecinos se
pierde ~30% del área con viento moderado y hasta ~80% con viento fuerte).

Cada celda guarda el minuto en que el frente la alcanza (`llegada`), de
donde salen el área y la velocidad en cada instante.

La API pública (constructor, puede_arder, iniciar_incendio, simular_paso,
.grid, .paso_actual) no cambia: app.py y main_prueba.py funcionan igual.
"""

import numpy as np

import modelo_rothermel as rothermel
from modelo_probabilidad import contenido_humedad_equilibrio

# --- Estados del terreno ---
ESTADO_QUEMADO = 0
ESTADO_VEGETACION_LIGERA = 1   # pasto / matorral (combustible ligero)
ESTADO_FUEGO = 2
ESTADO_URBANO = 3
ESTADO_AGUA = 4
ESTADO_SIN_COMBUSTIBLE = 5     # vías, suelo desnudo (cortafuego natural)
ESTADO_VEGETACION_DENSA = 6    # bosque / arbolado (combustible pesado)

ESTADOS_COMBUSTIBLES = (ESTADO_VEGETACION_LIGERA, ESTADO_VEGETACION_DENSA, ESTADO_URBANO)

_MINUTOS_POR_PASO = 15

# Lo urbano NO tiene modelo de Rothermel (es solo para combustible
# silvestre): se aproxima como una fracción de la velocidad del pasto en
# ese punto (exposición a radiación/pavesas) y arde más tiempo una vez
# encendido (incendio estructural). Heurística documentada.
_FACTOR_EXPOSICION_URBANA = 0.3
_RESIDENCIA_URBANA_MIN = 60

# Pendiente máxima considerada (tan θ): acota artefactos de la
# interpolación gruesa de elevación.
_PENDIENTE_MAXIMA = 3.0

# Clases de combustible muerto 1h/10h/100h: se definen por su tiempo de
# respuesta a la humedad ambiente (horas).
_TIEMPOS_RESPUESTA_H = np.array([1.0, 10.0, 100.0])

# Condición CFL: en cada subpaso el frente avanza como mucho media celda.
_CFL = 0.5


class SimuladorIncendio:
    def __init__(self, filas: int = 50, columnas: int = 50, tam_celda_m: float = 10,
                 grid_inicial: np.ndarray = None, elevacion: np.ndarray = None,
                 heterogeneidad: float = 0.0, semilla=None):
        """
        grid_inicial: matriz de estados ya construida (p. ej. con geografía
            real vía ingesta_geografica.rasterizar_geografia). Si no se da,
            se usa una grilla de puro pasto.
        elevacion: matriz de elevaciones (m) del MISMO tamaño que la
            grilla. Si es None no hay efecto de pendiente.
        heterogeneidad: desviación estándar (log) de un factor aleatorio
            fijo por celda sobre la velocidad, para representar combustible
            no uniforme. 0 = determinista.
        semilla: semilla de ese factor aleatorio (reproducibilidad).
        """
        self.filas = filas
        self.cols = columnas
        self.tam_celda_m = tam_celda_m

        if grid_inicial is not None:
            assert grid_inicial.shape == (filas, columnas), "grid_inicial no coincide con filas/columnas"
            self.grid = grid_inicial.copy()
        else:
            self.grid = np.full((filas, columnas), ESTADO_VEGETACION_LIGERA, dtype=int)

        self.elevacion = elevacion
        self.paso_actual = 0
        self.llegada = np.full((filas, columnas), np.inf)
        self.humedad_muerta = None
        self.lwr_max = 1.0

        self._terreno = self.grid.copy()
        self._combustible = np.isin(self._terreno, ESTADOS_COMBUSTIBLES)
        self._residencia = np.where(self._terreno == ESTADO_URBANO, _RESIDENCIA_URBANA_MIN, _MINUTOS_POR_PASO)
        # phi: distancia con signo al frente (se fija en iniciar_incendio).
        # Una celda sin combustible (velocidad 0) conserva su phi > 0 y el
        # esquema upwind es monótono, así que detrás de ella phi nunca baja
        # de ese valor: funciona como cortafuego sin tratamiento especial.
        self._phi = np.full((filas, columnas), 1e9)
        self._pendiente_tan, self._azimut_subida = self._pendiente()

        # ponytail: heterogeneidad = factor lognormal fijo por celda; un campo de
        # combustible espacialmente correlacionado lo reemplazaría si hiciera falta.
        rng = np.random.default_rng(semilla)
        self._factor = (np.exp(rng.normal(0.0, heterogeneidad, (filas, columnas)))
                        if heterogeneidad > 0 else np.ones((filas, columnas)))

    def _pendiente(self):
        """Magnitud (tan θ) y azimut cuesta arriba (0 = norte, 90 = este)
        de la pendiente de cada celda."""
        if self.elevacion is None:
            return np.zeros((self.filas, self.cols)), np.zeros((self.filas, self.cols))
        d_fila, d_col = np.gradient(self.elevacion, self.tam_celda_m)
        este, norte = d_col, -d_fila
        tan = np.clip(np.hypot(este, norte), 0.0, _PENDIENTE_MAXIMA)
        return tan, np.degrees(np.arctan2(este, norte)) % 360.0

    def puede_arder(self, fila: int, col: int, clima: dict) -> bool:
        """
        ¿La celda (fila, col) puede sostener combustión bajo este clima?

        Falso si no es combustible (agua, vía), si llueve, o si la humedad
        del combustible supera su humedad de extinción de Rothermel (12%
        pasto, 25% bosque): ahí R = 0 en cualquier dirección. Lo urbano usa
        el criterio del pasto, porque su velocidad es una fracción de esa.
        """
        if not (0 <= fila < self.filas and 0 <= col < self.cols):
            raise ValueError("Las coordenadas están fuera de la grilla.")

        estado = self.grid[fila, col]
        if estado not in ESTADOS_COMBUSTIBLES:
            return False
        if clima.get("precipitacion", 0.0) > 0.0:
            return False

        modelo = rothermel.FUEL_MODEL_DENSO if estado == ESTADO_VEGETACION_DENSA else rothermel.FUEL_MODEL_LIGERO
        return rothermel.velocidad_base(modelo, clima).r0_m_min > 0.0

    def iniciar_incendio(self, fila: int, col: int):
        """Enciende la celda de origen (la coordenada que ingresó el
        usuario). No verifica si la combustión es sostenible: eso es
        `puede_arder`."""
        if not (0 <= fila < self.filas and 0 <= col < self.cols):
            raise ValueError("Las coordenadas iniciales están fuera de la grilla.")
        fila_i, col_i = np.mgrid[0:self.filas, 0:self.cols]
        distancia = np.hypot(fila_i - fila, col_i - col) * self.tam_celda_m
        self._phi = np.minimum(self._phi, distancia - 0.5 * self.tam_celda_m)
        self.llegada[fila, col] = self.paso_actual * _MINUTOS_POR_PASO
        self.grid[fila, col] = ESTADO_FUEGO

    def _actualizar_humedad(self, clima: dict):
        """Humedad de combustible muerto (1h, 10h, 100h) que responde al
        clima con su tiempo de respuesta, en vez de igualar al instante la
        humedad de equilibrio. Arranca equilibrada con el primer clima."""
        emc = contenido_humedad_equilibrio(clima.get("temperatura", 25.0), clima.get("humedad_relativa", 50.0))
        if self.humedad_muerta is None:
            self.humedad_muerta = np.full(3, emc)
        else:
            # ponytail: la lluvia no moja el combustible aquí (solo pausa el avance);
            # modelar el mojado exige un modelo de humedad del combustible con lluvia.
            retencion = np.exp(-(_MINUTOS_POR_PASO / 60.0) / _TIEMPOS_RESPUESTA_H)
            self.humedad_muerta = emc + (self.humedad_muerta - emc) * retencion

    def _elipses(self, clima: dict, multiplicador: float):
        """Semiejes (a, b), desplazamiento del foco (c) y azimut de cabeza de
        la elipse de Huygens de cada celda, en m/min."""
        humedades = tuple(self.humedad_muerta)
        # Convención meteorológica: el viento VIENE de viento_direccion, así
        # que empuja el fuego hacia viento_direccion + 180.
        viento_hacia = (clima.get("viento_direccion", 0.0) + 180.0) % 360.0
        cabeza = np.zeros((self.filas, self.cols))
        cola = np.zeros((self.filas, self.cols))
        lwr = np.ones((self.filas, self.cols))
        azimut = np.zeros((self.filas, self.cols))
        for estado, modelo, factor in (
            (ESTADO_VEGETACION_LIGERA, rothermel.FUEL_MODEL_LIGERO, 1.0),
            (ESTADO_VEGETACION_DENSA, rothermel.FUEL_MODEL_DENSO, 1.0),
            (ESTADO_URBANO, rothermel.FUEL_MODEL_LIGERO, _FACTOR_EXPOSICION_URBANA),
        ):
            m = self._terreno == estado
            if not m.any():
                continue
            base = rothermel.velocidad_base(modelo, clima, humedades)
            rh, rb, l, az = rothermel.elipse_efectiva(base, viento_hacia, self._pendiente_tan[m], self._azimut_subida[m])
            cabeza[m], cola[m], lwr[m], azimut[m] = rh * factor, rb * factor, l, az
        # ponytail: el esquema upwind es isotrópico; con elipses muy alargadas
        # (LWR > 4) sobreestima el área de los flancos (+35% con LWR 8). La app
        # avisa con esto; la mejora es un Hamiltoniano de Godunov anisotrópico.
        lwr_este_paso = float(lwr[self._combustible].max()) if self._combustible.any() else 1.0
        self.lwr_max = max(self.lwr_max, lwr_este_paso)
        escala = multiplicador / self._factor
        a = 0.5 * (cabeza + cola) * escala
        c = 0.5 * (cabeza - cola) * escala
        return a, a / lwr, c, np.radians(azimut)

    def simular_paso(self, clima: dict, multiplicador_riesgo: float = 1.0):
        """Avanza el frente 15 minutos simulados con el clima de este paso."""
        self.paso_actual += 1
        t = float((self.paso_actual - 1) * _MINUTOS_POR_PASO)
        t_fin = float(self.paso_actual * _MINUTOS_POR_PASO)
        self._actualizar_humedad(clima)

        # Con lluvia el frente no avanza este paso.
        if clima.get("precipitacion", 0.0) <= 0.0:
            a, b, c, azimut = self._elipses(clima, multiplicador_riesgo)
            cab_este, cab_norte = np.sin(azimut), np.cos(azimut)
            h = self.tam_celda_m
            while t < t_fin:
                phi = self._phi
                # dx: oeste/este; dy_menos: fila de arriba (norte); dy_mas: fila de abajo (sur).
                dx_menos, dx_mas, dy_menos, dy_mas = _diferencias(phi, h)
                # Gradiente "upwind" de Osher-Sethian para un frente que solo se expande.
                gradiente = np.sqrt(np.maximum(dx_menos, 0) ** 2 + np.minimum(dx_mas, 0) ** 2
                                    + np.maximum(dy_menos, 0) ** 2 + np.minimum(dy_mas, 0) ** 2)
                # Normal exterior del frente (hacia lo no quemado).
                n_este = 0.5 * (dx_menos + dx_mas)
                n_norte = -0.5 * (dy_menos + dy_mas)
                norma = np.hypot(n_este, n_norte)
                sin_normal = norma == 0
                norma[sin_normal] = 1.0
                n_este, n_norte = n_este / norma, n_norte / norma
                # Función soporte de la elipse: velocidad del frente en esa normal.
                a_lo_largo = n_este * cab_este + n_norte * cab_norte
                a_traves = n_este * cab_norte - n_norte * cab_este
                velocidad = c * a_lo_largo + np.sqrt((a * a_lo_largo) ** 2 + (b * a_traves) ** 2)
                # Donde la normal no está definida (el punto de ignición, simétrico)
                # la velocidad no puede ser 0: esa celda quedaría congelada y su
                # vecina perdería el gradiente "upwind", frenando todo el frente.
                velocidad[sin_normal] = (a + c)[sin_normal]
                velocidad[~self._combustible] = 0.0

                v_max = velocidad.max()
                if v_max <= 0.0:
                    break
                dt = min(_CFL * h / v_max, t_fin - t)
                nuevo = phi - dt * velocidad * gradiente
                cruza = (phi > 0) & (nuevo <= 0)
                self.llegada[cruza] = t + dt * phi[cruza] / (phi[cruza] - nuevo[cruza])
                self._phi = _reinicializar(nuevo, h, self._combustible)
                t += dt

        llego = self.llegada <= t_fin
        en_llamas = llego & (self.llegada > t_fin - self._residencia)
        self.grid = np.where(llego, np.where(en_llamas, ESTADO_FUEGO, ESTADO_QUEMADO), self._terreno)


def _diferencias(phi, h):
    p = np.pad(phi, 1, mode="edge")
    return ((phi - p[1:-1, :-2]) / h, (p[1:-1, 2:] - phi) / h,
            (phi - p[:-2, 1:-1]) / h, (p[2:, 1:-1] - phi) / h)


def _reinicializar(phi0, h, combustible, iteraciones=2):
    """
    Devuelve phi como distancia con signo sin mover su contorno cero
    (Sussman, Smereka y Osher 1994, con la corrección de subcelda de Russo y
    Smereka 2000). Sin esto, lo quemado se aplana y ese quiebre, a media
    celda del frente, lo frena con el suavizado numérico.
    Las celdas sin combustible conservan su valor: siguen siendo cortafuego.
    """
    signo = np.sign(phi0)
    xm, xp, ym, yp = _diferencias(phi0, h)
    # Celdas junto al frente: distancia exacta a la interfaz por interpolación.
    p = np.pad(phi0, 1, mode="edge")
    vecinos = (p[1:-1, :-2], p[1:-1, 2:], p[:-2, 1:-1], p[2:, 1:-1])
    junto = np.zeros(phi0.shape, dtype=bool)
    for v in vecinos:
        junto |= signo * np.sign(v) < 0
    salto = np.maximum.reduce([np.abs(xp + xm) / 2 * h, np.abs(yp + ym) / 2 * h,
                               np.abs(xp) * h, np.abs(xm) * h, np.abs(yp) * h, np.abs(ym) * h, np.full(phi0.shape, 1e-12)])
    distancia_junto = h * phi0 / salto
    phi = phi0.copy()
    dtau = 0.5 * h
    for _ in range(iteraciones):
        xm, xp, ym, yp = _diferencias(phi, h)
        mas = np.sqrt(np.maximum(np.maximum(xm, 0) ** 2, np.minimum(xp, 0) ** 2)
                      + np.maximum(np.maximum(ym, 0) ** 2, np.minimum(yp, 0) ** 2))
        menos = np.sqrt(np.maximum(np.minimum(xm, 0) ** 2, np.maximum(xp, 0) ** 2)
                        + np.maximum(np.minimum(ym, 0) ** 2, np.maximum(yp, 0) ** 2))
        grad = np.where(signo > 0, mas, menos)
        lejos = phi - dtau * signo * (grad - 1.0)
        cerca = phi - (dtau / h) * (signo * np.abs(phi) - distancia_junto)
        phi = np.where(junto, cerca, lejos)
    return np.where(combustible, phi, phi0)
