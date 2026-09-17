"""
Autómata celular de propagación de incendios.

Cambios clave respecto a la versión original:

1. VECTORIZADO con numpy: la velocidad de propagación en una dirección
   (dx, dy) se calcula a partir de un clima uniforme sobre la grilla en
   un paso dado, así que la parte cara del cálculo (física de Rothermel)
   se hace UNA vez por dirección y tipo de combustible (no una vez por
   celda). Esto permite grillas más grandes/finas sin volverse lento.

2. TIPOS DE COMBUSTIBLE: pasto/matorral y bosque denso usan cada uno su
   propio modelo de combustible estándar de Rothermel (ver
   `modelo_rothermel.py`); la zona urbana no tiene un modelo de Rothermel
   propio (ese modelo es solo para combustible silvestre) y usa una
   heurística de exposición estructural aparte.

3. PENDIENTE DEL TERRENO: si hay un modelo de elevación disponible, la
   pendiente real (por dirección) alimenta el coeficiente de pendiente
   de Rothermel (1972): el fuego se propaga más rápido cuesta arriba y
   más lento cuesta abajo.

La celda de origen (la coordenada exacta que dio el usuario) es donde
`iniciar_incendio` enciende el fuego; no se rastrea aparte como "la
casa" porque el incendio siempre empieza justo ahí, así que ese
seguimiento nunca aportaba información (el origen siempre está "en
llamas" desde el paso 0).
"""

import numpy as np

import modelo_rothermel as rothermel

# --- Estados del terreno ---
ESTADO_QUEMADO = 0
ESTADO_VEGETACION_LIGERA = 1   # pasto / matorral (combustible ligero)
ESTADO_FUEGO = 2
ESTADO_URBANO = 3
ESTADO_AGUA = 4
ESTADO_SIN_COMBUSTIBLE = 5     # vías, suelo desnudo (cortafuego natural)
ESTADO_VEGETACION_DENSA = 6    # bosque / arbolado (combustible pesado)

ESTADOS_COMBUSTIBLES = (ESTADO_VEGETACION_LIGERA, ESTADO_VEGETACION_DENSA, ESTADO_URBANO)

_NUM_ESTADOS = 7
_MINUTOS_POR_PASO = 15

# Lo urbano NO tiene modelo de Rothermel (ese modelo es solo para
# combustible silvestre: pasto/bosque). Se aproxima como una fracción de
# la velocidad que tendría la vegetación ligera bajo el mismo viento y
# pendiente en ese punto -- representa exposición a radiación/pavesas de
# celdas vecinas en llamas, no combustión de materiales de construcción.
# Es más resistente a encender (factor bajo) pero, heurísticamente, arde
# más pasos una vez encendido (incendio estructural).
_FACTOR_EXPOSICION_URBANA = 0.3
_DURACION_COMBUSTIBLE = np.zeros(_NUM_ESTADOS, dtype=int)
_DURACION_COMBUSTIBLE[ESTADO_VEGETACION_LIGERA] = rothermel.pasos_combustion(
    rothermel.FUEL_MODEL_LIGERO, _MINUTOS_POR_PASO)
_DURACION_COMBUSTIBLE[ESTADO_VEGETACION_DENSA] = rothermel.pasos_combustion(
    rothermel.FUEL_MODEL_DENSO, _MINUTOS_POR_PASO)
_DURACION_COMBUSTIBLE[ESTADO_URBANO] = 4  # heurística estructural, no Rothermel

# Las 8 direcciones de la vecindad de Moore.
_DIRECCIONES = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]

# Pendiente máxima considerada (fracción rise/run = tan(theta)); acota el
# coeficiente de pendiente de Rothermel para que la interpolación gruesa
# de elevación no produzca valores patológicos en bordes/artefactos.
_PENDIENTE_MAXIMA = 3.0


def _valor_vecino(matriz: np.ndarray, di: int, dj: int, relleno):
    """
    Para cada celda (i, j), retorna matriz[i+di, j+dj], rellenando con
    `relleno` donde el vecino cae fuera de la grilla.
    """
    filas, columnas = matriz.shape
    resultado = np.full((filas, columnas), relleno, dtype=matriz.dtype)

    src_f = slice(di, filas) if di >= 0 else slice(0, filas + di)
    dst_f = slice(0, filas - di) if di >= 0 else slice(-di, filas)
    src_c = slice(dj, columnas) if dj >= 0 else slice(0, columnas + dj)
    dst_c = slice(0, columnas - dj) if dj >= 0 else slice(-dj, columnas)

    resultado[dst_f, dst_c] = matriz[src_f, src_c]
    return resultado


class SimuladorIncendio:
    def __init__(self, filas: int = 50, columnas: int = 50, tam_celda_m: float = 10,
                 grid_inicial: np.ndarray = None, elevacion: np.ndarray = None):
        """
        grid_inicial: matriz de estados ya construida (por ejemplo, con
            geografía real vía ingesta_geografica.rasterizar_geografia).
            Si no se da, se usa una grilla de puro pasto.
        elevacion: matriz de elevaciones en metros, del MISMO tamaño que
            la grilla (filas x columnas). Si es None, no hay efecto de
            pendiente (equivale a terreno plano).
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
        self.tiempo_fuego = np.zeros((filas, columnas), dtype=int)

        self.paso_actual = 0

    def iniciar_incendio(self, fila: int, col: int):
        """Enciende la celda de origen del incendio (la coordenada exacta
        que ingresó el usuario, asumiendo que ahí empieza el fuego)."""
        if not (0 <= fila < self.filas and 0 <= col < self.cols):
            raise ValueError("Las coordenadas iniciales están fuera de la grilla.")
        estado_previo = self.grid[fila, col]
        self.grid[fila, col] = ESTADO_FUEGO
        duracion = _DURACION_COMBUSTIBLE[estado_previo]
        self.tiempo_fuego[fila, col] = duracion if duracion > 0 else 3

    def _pendiente_direccional(self, di: int, dj: int) -> np.ndarray:
        """Array (filas x columnas) con la pendiente (tan(theta), fracción
        rise/run) en la dirección (di, dj), para el coeficiente de
        pendiente de Rothermel. Si no hay modelo de elevación, retorna
        0.0 (sin efecto) en toda la grilla."""
        if self.elevacion is None:
            return np.zeros((self.filas, self.cols))

        # (di, dj) apunta de la celda destino hacia la celda vecina en
        # llamas (la posible fuente de ignición): destino = origen + (di,dj).
        # La pendiente relevante es "destino menos origen": positiva si el
        # fuego avanza cuesta arriba (debe propagarse más rápido).
        distancia_m = self.tam_celda_m * np.hypot(di, dj)
        elevacion_origen = _valor_vecino(self.elevacion, di, dj, relleno=0.0)
        pendiente = (self.elevacion - elevacion_origen) / distancia_m
        return np.clip(pendiente, -_PENDIENTE_MAXIMA, _PENDIENTE_MAXIMA)

    def simular_paso(self, clima: dict, multiplicador_riesgo: float = 1.0):
        self.paso_actual += 1
        grid = self.grid
        tiempo = self.tiempo_fuego

        # 1. Las celdas ya en llamas consumen un paso de su tiempo de combustión.
        en_fuego = grid == ESTADO_FUEGO
        tiempo[en_fuego] -= 1
        apagadas = en_fuego & (tiempo <= 0)
        grid[apagadas] = ESTADO_QUEMADO

        # Para efectos de contagio, el fuego "activo" durante este paso es
        # el que existía ANTES de apagar lo que ya se consumió.
        fuego_activo = en_fuego

        # Si llovió, no hay ignición posible en ninguna dirección este paso
        # (las celdas ya en llamas siguen consumiéndose arriba con normalidad).
        if clima.get("precipitacion", 0.0) > 0.0:
            return

        combustible = np.isin(grid, ESTADOS_COMBUSTIBLES)
        duracion_celda = _DURACION_COMBUSTIBLE[grid]

        nuevo_ignitado = np.zeros((self.filas, self.cols), dtype=bool)

        # Física de Rothermel: se calcula UNA vez por tipo de combustible
        # por paso (el clima es uniforme sobre la grilla), no por celda.
        base_ligero = rothermel.velocidad_base(rothermel.FUEL_MODEL_LIGERO, clima)
        base_denso = rothermel.velocidad_base(rothermel.FUEL_MODEL_DENSO, clima)
        lwr_ligero = rothermel.razon_largo_ancho(rothermel.FUEL_MODEL_LIGERO, clima)
        lwr_denso = rothermel.razon_largo_ancho(rothermel.FUEL_MODEL_DENSO, clima)
        viento_direccion = clima.get("viento_direccion", 0.0)

        es_ligero = grid == ESTADO_VEGETACION_LIGERA
        es_denso = grid == ESTADO_VEGETACION_DENSA
        es_urbano = grid == ESTADO_URBANO

        for (di, dj) in _DIRECCIONES:
            pendiente = self._pendiente_direccional(di, dj)
            angulo_direccion_deg = np.degrees(np.arctan2(di, dj)) % 360

            r_ligero = rothermel.velocidad_direccional(
                base_ligero, lwr_ligero, viento_direccion, pendiente, angulo_direccion_deg)
            r_denso = rothermel.velocidad_direccional(
                base_denso, lwr_denso, viento_direccion, pendiente, angulo_direccion_deg)
            r_urbano = r_ligero * _FACTOR_EXPOSICION_URBANA

            r_direccion = np.select(
                [es_ligero, es_denso, es_urbano], [r_ligero, r_denso, r_urbano], default=0.0)

            # Velocidad (m/min) -> fracción de celda recorrida en este paso.
            p_grid = np.clip(
                r_direccion * multiplicador_riesgo * _MINUTOS_POR_PASO / self.tam_celda_m, 0.0, 1.0)

            vecino_en_fuego = _valor_vecino(fuego_activo, di, dj, relleno=False)
            azar = np.random.rand(self.filas, self.cols)

            exito = vecino_en_fuego & combustible & (azar < p_grid)
            nuevo_ignitado |= exito

        if np.any(nuevo_ignitado):
            grid[nuevo_ignitado] = ESTADO_FUEGO
            tiempo[nuevo_ignitado] = duracion_celda[nuevo_ignitado]
