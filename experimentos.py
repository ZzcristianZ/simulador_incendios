"""
Laboratorio de sensibilidad: responde la pregunta del proyecto --¿cómo
influyen los cambios en los parámetros ambientales y del terreno sobre la
velocidad de propagación y el área afectada a lo largo del tiempo?--
variando UN parámetro a la vez sobre un terreno controlado (plano o con
pendiente conocida, un solo combustible) y registrando velocidad de
cabeza y área paso a paso.

Uso:  python experimentos.py
Escribe resultados/barrido.csv y un PNG por parámetro en resultados/.
"""

import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from entorno_simulacion import construir_clima_manual, terreno_controlado
from metricas_fuego import CalculadorMetricas
from simulador_automata import SimuladorIncendio, ESTADO_VEGETACION_LIGERA, ESTADO_VEGETACION_DENSA

TAM_CELDA_M = 10
MINUTOS_POR_PASO = 15
LADO = 201  # 2 km x 2 km
PASOS = 8   # 2 horas

CLIMA_BASE = {
    "temperatura": 30.0, "humedad_relativa": 35.0, "viento_velocidad": 3.0, "viento_rafagas": 4.0,
    "viento_direccion": 270.0, "precipitacion": 0.0, "radiacion_solar": 600.0,
    "humedad_suelo": 0.2, "vpd": 2.0,
}
TERRENO_BASE = {"pendiente_pct": 0.0, "combustible": ESTADO_VEGETACION_DENSA}
NOMBRES_COMBUSTIBLE = {ESTADO_VEGETACION_LIGERA: "pasto", ESTADO_VEGETACION_DENSA: "bosque"}

BARRIDOS = {
    "viento_velocidad": [0.0, 2.0, 4.0, 6.0],
    "humedad_relativa": [20.0, 35.0, 50.0, 65.0],
    "temperatura": [20.0, 25.0, 30.0, 35.0],
    "humedad_combustible_vivo": [60.0, 100.0, 140.0],
    "pendiente_pct": [0.0, 15.0, 30.0, 45.0],
    "combustible": [ESTADO_VEGETACION_LIGERA, ESTADO_VEGETACION_DENSA],
}


def correr(clima: dict, pendiente_pct: float, combustible: int, pasos: int = PASOS, lado: int = LADO) -> list:
    """Una corrida sobre terreno controlado (la pendiente sube hacia el este,
    a favor del viento base). Devuelve una fila por paso."""
    terreno = terreno_controlado(lado, lado, TAM_CELDA_M, pendiente_pct, 90.0, combustible)
    serie, _, _ = construir_clima_manual(clima)
    sim = SimuladorIncendio(lado, lado, TAM_CELDA_M, grid_inicial=terreno["grid"], elevacion=terreno["elevacion"])
    origen = terreno["celda_origen"]
    metricas = CalculadorMetricas(TAM_CELDA_M, MINUTOS_POR_PASO, origen=origen)
    arde = sim.puede_arder(*origen, serie[0])
    if arde:
        sim.iniciar_incendio(*origen)
    filas = []
    for paso in range(1, pasos + 1):
        if arde:
            sim.simular_paso(serie[0])
        rep = metricas.generar_reporte(terreno["grid"], sim.grid, paso)
        quemado = sim.llegada <= paso * MINUTOS_POR_PASO
        filas.append({
            "minuto": rep["tiempo_minutos"],
            "area_ha": rep["area_hectareas"] if arde else 0.0,
            "velocidad_m_min": rep["velocidad_m_min"] if arde else 0.0,
            # Si el fuego toca el borde, el área deja de ser comparable (se sale de la grilla).
            "toca_borde": bool(quemado[0].any() or quemado[-1].any() or quemado[:, 0].any() or quemado[:, -1].any()),
            "lwr_max": round(sim.lwr_max, 2),
        })
    return filas


def barrido(parametro: str, valores: list, pasos: int = PASOS, lado: int = LADO) -> list:
    """Varía un solo parámetro (del clima o del terreno) dejando el resto en su valor base."""
    filas = []
    for valor in valores:
        clima, terreno = dict(CLIMA_BASE), dict(TERRENO_BASE)
        (terreno if parametro in terreno else clima)[parametro] = valor
        for fila in correr(clima, terreno["pendiente_pct"], terreno["combustible"], pasos, lado):
            filas.append({"parametro": parametro, "valor": valor, **fila})
    return filas


def _graficar(parametro: str, filas: list, ruta: str):
    fig, (ax_v, ax_a) = plt.subplots(1, 2, figsize=(10, 4))
    for valor in dict.fromkeys(f["valor"] for f in filas):
        serie = [f for f in filas if f["valor"] == valor]
        etiqueta = NOMBRES_COMBUSTIBLE.get(valor, valor) if parametro == "combustible" else valor
        minutos = [f["minuto"] for f in serie]
        ax_v.plot(minutos, [f["velocidad_m_min"] for f in serie], marker="o", label=str(etiqueta))
        ax_a.plot(minutos, [f["area_ha"] for f in serie], marker="o", label=str(etiqueta))
    ax_v.set(xlabel="minutos simulados", ylabel="velocidad de cabeza (m/min)", title=parametro)
    ax_a.set(xlabel="minutos simulados", ylabel="área afectada (ha)", title=parametro)
    ax_a.legend(title=parametro)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def main(carpeta: str = "resultados"):
    os.makedirs(carpeta, exist_ok=True)
    todas = []
    for parametro, valores in BARRIDOS.items():
        filas = barrido(parametro, valores)
        todas += filas
        _graficar(parametro, filas, os.path.join(carpeta, f"barrido_{parametro}.png"))
        print(f"{parametro}: listo")
    with open(os.path.join(carpeta, "barrido.csv"), "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(todas[0]))
        escritor.writeheader()
        escritor.writerows(todas)


if __name__ == "__main__":
    main()
