"""
Autómata celular de propagación de incendios.

Cambios clave respecto a la versión original:

1. VECTORIZADO con numpy: la probabilidad climática de ignición en una
   dirección (dx, dy) es la misma para toda la grilla en un paso dado
   (el clima es uniforme sobre el área simulada), así que se calcula
   UNA vez por dirección (8 valores) en vez de una vez por cada celda
   vecina. Esto permite grillas más grandes/finas sin volverse lento.

2. TIPOS DE COMBUSTIBLE: pasto/matorral, bosque denso y zona urbana ya
   no comparten la misma resistencia ni el mismo tiempo de combustión.

3. PENDIENTE DEL TERRENO: si hay un modelo de elevación disponible, el
   fuego se propaga más rápido cuesta arriba y más lento cuesta abajo
   (aproximación exponencial simplificada, en la línea de Alexandridis
   et al. 2008).

4. SEGUIMIENTO DE "LA CASA": se puede marcar una celda específica (la
   coordenada exacta que dio el usuario) y el autómata registra en qué
   paso se incendia, si es que ocurre.
"""

import numpy as np

# --- Estados del terreno ---
ESTADO_QUEMADO = 0
ESTADO_VEGETACION_LIGERA = 1   # pasto / matorral (combustible ligero)
ESTADO_FUEGO = 2
ESTADO_URBANO = 3
ESTADO_AGUA = 4
ESTADO_SIN_COMBUSTIBLE = 5     # vías, suelo desnudo (cortafuego natural)
ESTADO_VEGETACION_DENSA = 6    # bosque / arbolado (combustible pesado)

ESTADOS_COMBUSTIBLES = (ESTADO_VEGETACION_LIGERA, ESTADO_VEGETACION_DENSA, ESTADO_URBANO)

# Propiedades por tipo de combustible:
#   factor: qué tan fácil/difícil es que ese tipo de celda se encienda
#           (fuel load / resistencia estructural combinados).
#   duracion: cuántos pasos de 15 min arde antes de consumirse.
_NUM_ESTADOS = 7
_FACTOR_COMBUSTIBLE = np.zeros(_NUM_ESTADOS)
_FACTOR_COMBUSTIBLE[ESTADO_VEGETACION_LIGERA] = 0.8
_FACTOR_COMBUSTIBLE[ESTADO_VEGETACION_DENSA] = 1.4
_FACTOR_COMBUSTIBLE[ESTADO_URBANO] = 0.3  # más resistente a encenderse

_DURACION_COMBUSTIBLE = np.zeros(_NUM_ESTADOS, dtype=int)
_DURACION_COMBUSTIBLE[ESTADO_VEGETACION_LIGERA] = 2
_DURACION_COMBUSTIBLE[ESTADO_VEGETACION_DENSA] = 5
_DURACION_COMBUSTIBLE[ESTADO_URBANO] = 4

# Las 8 direcciones de la vecindad de Moore.
_DIRECCIONES = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]

# Constante empírica del factor de pendiente (simplificación de la forma
# exp(a * tan(theta)) usada en modelos de autómata celular de incendios).
_K_PENDIENTE = 0.06


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

        self.celda_casa = None
        self.paso_actual = 0
        self.paso_casa_incendiada = None

    def definir_casa(self, fila: int, col: int):
        """Marca la celda que representa la ubicación exacta del usuario."""
        self.celda_casa = (int(fila), int(col))
        if self.grid[self.celda_casa] == ESTADO_FUEGO and self.paso_casa_incendiada is None:
            self.paso_casa_incendiada = self.paso_actual

    def iniciar_incendio(self, fila: int, col: int):
        if not (0 <= fila < self.filas and 0 <= col < self.cols):
            raise ValueError("Las coordenadas iniciales están fuera de la grilla.")
        estado_previo = self.grid[fila, col]
        self.grid[fila, col] = ESTADO_FUEGO
        duracion = _DURACION_COMBUSTIBLE[estado_previo]
        self.tiempo_fuego[fila, col] = duracion if duracion > 0 else 3
        if self.celda_casa == (fila, col) and self.paso_casa_incendiada is None:
            self.paso_casa_incendiada = self.paso_actual

    def _factor_pendiente(self, di: int, dj: int) -> np.ndarray:
        """Array (filas x columnas) con el factor de pendiente para la
        dirección (di, dj). Si no hay modelo de elevación, retorna 1.0
        (sin efecto) en toda la grilla."""
        if self.elevacion is None:
            return np.ones((self.filas, self.cols))

        # (di, dj) apunta de la celda destino hacia la celda vecina en
        # llamas (la posible fuente de ignición): destino = origen + (di,dj).
        # La pendiente relevante es "destino menos origen": positiva si el
        # fuego avanza cuesta arriba (debe propagarse más rápido).
        distancia_m = self.tam_celda_m * np.hypot(di, dj)
        elevacion_origen = _valor_vecino(self.elevacion, di, dj, relleno=0.0)
        pendiente_pct = (self.elevacion - elevacion_origen) / distancia_m * 100.0
        factor = np.exp(_K_PENDIENTE * pendiente_pct)
        return np.clip(factor, 0.2, 5.0)

    def simular_paso(self, clima: dict, multiplicador_riesgo: float = 1.0):
        from modelo_probabilidad import calcular_probabilidad_ignicion

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

        combustible = np.isin(grid, ESTADOS_COMBUSTIBLES)
        factor_celda = _FACTOR_COMBUSTIBLE[grid]
        duracion_celda = _DURACION_COMBUSTIBLE[grid]

        nuevo_ignitado = np.zeros((self.filas, self.cols), dtype=bool)

        for (di, dj) in _DIRECCIONES:
            p_clima = calcular_probabilidad_ignicion(clima, dx=dj, dy=di)
            if p_clima <= 0.0:
                continue

            vecino_en_fuego = _valor_vecino(fuego_activo, di, dj, relleno=False)
            f_pendiente = self._factor_pendiente(di, dj)

            p_grid = np.clip(p_clima * f_pendiente * multiplicador_riesgo * factor_celda, 0.0, 1.0)
            azar = np.random.rand(self.filas, self.cols)

            exito = vecino_en_fuego & combustible & (azar < p_grid)
            nuevo_ignitado |= exito

        if np.any(nuevo_ignitado):
            grid[nuevo_ignitado] = ESTADO_FUEGO
            tiempo[nuevo_ignitado] = duracion_celda[nuevo_ignitado]

        # Seguimiento del destino de "la casa" del usuario.
        if self.celda_casa is not None and self.paso_casa_incendiada is None:
            if nuevo_ignitado[self.celda_casa]:
                self.paso_casa_incendiada = self.paso_actual

    def estado_casa(self) -> dict:
        """Resumen legible del estado actual de la celda 'casa'."""
        if self.celda_casa is None:
            return {"definida": False}

        estado_actual = self.grid[self.celda_casa]
        minutos_por_paso = 15

        if estado_actual == ESTADO_FUEGO or self.paso_casa_incendiada is not None:
            paso = self.paso_casa_incendiada if self.paso_casa_incendiada is not None else self.paso_actual
            return {
                "definida": True,
                "estado": "en_llamas" if estado_actual == ESTADO_FUEGO else "destruida",
                "minuto": paso * minutos_por_paso,
            }
        if estado_actual == ESTADO_QUEMADO:
            return {"definida": True, "estado": "destruida", "minuto": self.paso_actual * minutos_por_paso}

        return {"definida": True, "estado": "a_salvo", "minuto": None}
