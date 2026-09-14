import numpy as np
from modelo_probabilidad import calcular_probabilidad_ignicion

# Definición de Estados del Terreno
ESTADO_QUEMADO = 0
ESTADO_VEGETACION = 1
ESTADO_FUEGO = 2
ESTADO_URBANO = 3
ESTADO_AGUA = 4

class SimuladorIncendio:
    def __init__(self, filas: int = 50, columnas: int = 50, tam_celda_m: int = 10):
        self.filas = filas
        self.cols = columnas
        self.tam_celda_m = tam_celda_m
        self.grid = np.ones((filas, columnas), dtype=int)
        
        # Matriz de tiempo restante de combustión por celda
        self.tiempo_fuego = np.zeros((filas, columnas), dtype=int)
        
        # Definimos una barrera natural de agua (4) en una sección
        self.grid[10:15, :] = ESTADO_AGUA
        # Definimos un asentamiento urbano (3) en el extremo derecho
        self.grid[30:45, 35:45] = ESTADO_URBANO

    def iniciar_incendio(self, fila: int, col: int):
        if 0 <= fila < self.filas and 0 <= col < self.cols:
            self.grid[fila, col] = ESTADO_FUEGO
            self.tiempo_fuego[fila, col] = 3  # Arde durante 3 pasos de tiempo
        else:
            raise ValueError("Las coordenadas iniciales están fuera de la grilla.")

    def simular_paso(self, clima: dict, multiplicador_riesgo: float = 1.0):
        nuevo_grid = self.grid.copy()
        nuevo_tiempo = self.tiempo_fuego.copy()
        
        vecinos = [
            (-1, -1), (-1, 0), (-1, 1),
            ( 0, -1),          ( 0, 1),
            ( 1, -1), ( 1, 0), ( 1, 1)
        ]
        
        for i in range(self.filas):
            for j in range(self.cols):
                # Si la celda está ardiendo, reducimos su tiempo de combustión
                if self.grid[i, j] == ESTADO_FUEGO:
                    nuevo_tiempo[i, j] -= 1
                    if nuevo_tiempo[i, j] <= 0:
                        nuevo_grid[i, j] = ESTADO_QUEMADO
                        
                # Si la celda es vegetación o urbana, evaluamos riesgo de ignición
                elif self.grid[i, j] in [ESTADO_VEGETACION, ESTADO_URBANO]:
                    for di, dj in vecinos:
                        ni, nj = i + di, j + dj
                        if 0 <= ni < self.filas and 0 <= nj < self.cols:
                            if self.grid[ni, nj] == ESTADO_FUEGO:
                                factor_resistencia = 0.5 if self.grid[i, j] == ESTADO_URBANO else 1.0
                                p_ignicion = calcular_probabilidad_ignicion(clima, dx=dj, dy=di) * factor_resistencia * multiplicador_riesgo
                                
                                if np.random.rand() < p_ignicion:
                                    nuevo_grid[i, j] = ESTADO_FUEGO
                                    nuevo_tiempo[i, j] = 3  # Arde durante 3 pasos
                                    break
                                    
        self.grid = nuevo_grid
        self.tiempo_fuego = nuevo_tiempo