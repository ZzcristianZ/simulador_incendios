"""
Velocidad de propagación superficial del fuego (Rothermel 1972) + forma
elíptica del incendio por efecto del viento (Anderson 1983).

Responsabilidad ÚNICA de este módulo: dado un tipo de combustible (modelo
de combustible estándar), el clima del paso y la pendiente local por
dirección, calcular la velocidad de propagación REAL (m/min) del frente de
fuego en cada una de las 8 direcciones de la vecindad de Moore.

Reemplaza la fórmula multiplicativa ad-hoc que tenía el proyecto (ver
`modelo_probabilidad.py`, que ahora solo calcula el índice Fosberg
informativo) por un modelo de combustión publicado y verificable.

Fuentes (verificadas en vivo, no de memoria, durante el diseño de este
módulo -- ver el plan de la sesión que lo introdujo):

- Parámetros de los modelos de combustible estándar (carga por clase de
  tamaño, razón superficie/volumen, profundidad de la cama de combustible,
  humedad de extinción): Anderson, H.E. (1982) "Aids to Determining Fuel
  Models for Estimating Fire Behavior", USDA GTR-INT-122. Tabla verificada
  contra github.com/firestarter-io/fuelmodels (src/FBFM13.json), que a su
  vez cita a Anderson (1982) y Andrews (2018).
- Ecuaciones núcleo (packing ratio, velocidad de reacción óptima,
  intensidad de reacción con amortiguación por humedad y minerales, flujo
  de propagación, coeficientes de viento y pendiente, sumidero de calor):
  Rothermel, R.C. (1972) "A Mathematical Model for Predicting Fire Spread
  in Wildland Fuels", USDA GTR-INT-115, con el refinamiento del
  coeficiente de viento de Albini, F.A. (1976) GTR-INT-30. Implementación
  portada y verificada contra el código fuente real del paquete R
  `Rothermel` (Vacchiano, G. & Ascoli, D. 2015, "An Implementation of the
  Rothermel Fire Spread Model in the R Programming Language", Fire
  Technology 51(3); github.com/cran/Rothermel, R/ros.R).
- Razón largo/ancho de la elipse de propagación por viento: Anderson, H.E.
  (1983) "Predicting Wind-Driven Wild Land Fire Size and Shape", USDA
  Research Paper INT-305 (la misma fórmula que usa FARSITE/BehavePlus).
- Tiempo de residencia de llama: Anderson, H.E. (1969) "Heat Transfer and
  Fire Spread", USDA Research Paper INT-69, tr = 384/sigma (minutos).

Simplificaciones deliberadas (documentadas también en el README):
- Solo se modelan 2 tipos de combustible silvestre (pasto y bosque real),
  porque la clasificación de vegetación de este proyecto viene únicamente
  de OpenStreetMap (sin una fuente global de cobertura de suelo).
- La humedad de los combustibles vivos (solo aplica al modelo de bosque,
  que tiene una fracción de leña viva) no tiene fuente climática en tiempo
  real; se usa una constante estacional típica documentada abajo.
- Viento y pendiente se combinan de forma aditiva, como en la fórmula
  original de Rothermel (1 + phi_viento + phi_pendiente), en vez de
  combinar vectorialmente dos elipses (viento y pendiente) como hace
  FARSITE -- ese nivel de detalle queda como extensión futura.
- Lo urbano NO es un modelo de Rothermel (que es solo para combustible
  silvestre): se mantiene como una heurística de exposición estructural
  claramente separada.
"""

from dataclasses import dataclass

import numpy as np

from modelo_probabilidad import contenido_humedad_equilibrio

# --- Constantes universales de Rothermel (no dependen del modelo de combustible) ---
_RHO_PARTICULA = 32.0       # lb/ft^3, densidad de partícula seca (estándar)
_CONTENIDO_MINERAL_TOTAL = 0.0555     # st, fracción (estándar)
_CONTENIDO_MINERAL_EFECTIVO = 0.01    # se, fracción (estándar)
_HEAT_CONTENT_BTU_LB = 8000.0         # h, estándar para los 13 modelos de Anderson
_NS = 0.174 * _CONTENIDO_MINERAL_EFECTIVO ** (-0.19)  # amortiguación mineral

# SAV (razón superficie/volumen, ft^-1) estándar para clases 10-hr y 100-hr:
# no varían por modelo de combustible (Albini 1976 / convención NWCG).
_SAV_10H = 109.0
_SAV_100H = 30.0

_TONS_ACRE_A_LB_FT2 = 2000.0 / 43560.0  # 1 ton corta/acre -> lb/ft^2


@dataclass(frozen=True)
class ModeloCombustible:
    """Un modelo de combustible estándar de Anderson (1982), en unidades
    Rothermel (lb/ft^2, ft^-1, ft, %). `reduccion_viento` es el factor de
    reducción de viento de 10 m a altura de llama media (NWCG, estándar:
    ~0.4 en campo abierto, ~0.2 bajo dosel de bosque)."""
    nombre: str
    carga_1h: float
    carga_10h: float
    carga_100h: float
    carga_herbacea_viva: float
    carga_lenosa_viva: float
    sav_1h: float
    sav_herbacea_viva: float
    sav_lenosa_viva: float
    profundidad_ft: float
    humedad_extincion_muerta: float  # %
    reduccion_viento: float
    humedad_viva_estacional: float = 100.0  # % -- constante documentada, sin fuente en vivo


# FBFM1 "Short grass (1 ft)" -> vegetación ligera / pasto.
FUEL_MODEL_LIGERO = ModeloCombustible(
    nombre="FBFM1 - Pasto corto",
    carga_1h=0.74 * _TONS_ACRE_A_LB_FT2,
    carga_10h=0.0, carga_100h=0.0,
    carga_herbacea_viva=0.0, carga_lenosa_viva=0.0,
    sav_1h=3500.0, sav_herbacea_viva=0.0, sav_lenosa_viva=0.0,
    profundidad_ft=1.0,
    humedad_extincion_muerta=12.0,
    reduccion_viento=0.4,
)

# FBFM10 "Timber (litter and understory)" -> vegetación densa / bosque real.
FUEL_MODEL_DENSO = ModeloCombustible(
    nombre="FBFM10 - Bosque (hojarasca y sotobosque)",
    carga_1h=3.01 * _TONS_ACRE_A_LB_FT2,
    carga_10h=2.00 * _TONS_ACRE_A_LB_FT2,
    carga_100h=5.01 * _TONS_ACRE_A_LB_FT2,
    carga_herbacea_viva=0.0, carga_lenosa_viva=2.00 * _TONS_ACRE_A_LB_FT2,
    sav_1h=2000.0, sav_herbacea_viva=0.0, sav_lenosa_viva=1500.0,
    profundidad_ft=1.0,
    humedad_extincion_muerta=25.0,
    reduccion_viento=0.2,
    humedad_viva_estacional=100.0,
)


@dataclass(frozen=True)
class _ResultadoBase:
    r0_m_min: float       # velocidad en llano, sin viento (m/min)
    phi_viento: float     # coeficiente de viento de Rothermel (adimensional)
    beta: float           # packing ratio (para el coeficiente de pendiente)
    tiempo_residencia_min: float


def _componentes(modelo: ModeloCombustible):
    """Las 5 clases de combustible (1h, 10h, 100h, herbácea viva, leñosa
    viva) como arrays paralelos de carga y SAV, en unidades Rothermel."""
    cargas = np.array([
        modelo.carga_1h, modelo.carga_10h, modelo.carga_100h,
        modelo.carga_herbacea_viva, modelo.carga_lenosa_viva,
    ])
    savs = np.array([
        modelo.sav_1h, _SAV_10H, _SAV_100H,
        modelo.sav_herbacea_viva, modelo.sav_lenosa_viva,
    ])
    return cargas, savs


def velocidad_base(modelo: ModeloCombustible, clima: dict) -> _ResultadoBase:
    """
    Velocidad de propagación en llano (sin pendiente) en la dirección del
    viento, más el coeficiente de viento y el packing ratio (necesario
    para el coeficiente de pendiente). Se calcula UNA vez por paso por
    modelo de combustible (el clima es uniforme sobre la grilla), no por
    celda -- igual que el resto del proyecto.
    """
    cargas, savs = _componentes(modelo)
    delta = modelo.profundidad_ft

    es_muerto = np.array([True, True, True, False, False])
    con_carga = cargas > 0.0

    humedad_muerta = contenido_humedad_equilibrio(
        clima.get("temperatura", 25.0), clima.get("humedad_relativa", 50.0)
    ) / 100.0
    humedad_viva = modelo.humedad_viva_estacional / 100.0
    humedades = np.where(es_muerto, humedad_muerta, humedad_viva)

    # Packing ratio (no depende de humedad ni viento).
    beta = np.sum(cargas / _RHO_PARTICULA) / delta if delta > 0 else 0.0

    hay_muerto = np.any(con_carga & es_muerto)
    hay_vivo = np.any(con_carga & ~es_muerto)

    if not hay_muerto and not hay_vivo:
        return _ResultadoBase(0.0, 0.0, beta, 1.0)

    # Fracciones de área por clase (Rothermel 1972, eq. 53-56).
    a = savs * cargas / _RHO_PARTICULA
    a_muerto = np.sum(np.where(es_muerto, a, 0.0))
    a_vivo = np.sum(np.where(~es_muerto, a, 0.0))
    a_tot = a_muerto + a_vivo

    f = np.zeros(5)
    if a_muerto > 0:
        f[:3] = np.where(a_muerto > 0, a[:3] / a_muerto, 0.0)
    if a_vivo > 0:
        f[3:] = a[3:] / a_vivo

    f_muerto = a_muerto / a_tot if a_tot > 0 else 0.0
    f_vivo = a_vivo / a_tot if a_tot > 0 else 0.0

    # Humedad de extinción de los combustibles vivos (Rothermel 1972 / Albini 1976).
    mx_muerta = modelo.humedad_extincion_muerta / 100.0
    if hay_vivo:
        w_exp = cargas[:3] * np.exp(-138.0 / np.where(savs[:3] > 0, savs[:3], 1.0))
        w_exp_sum = np.sum(np.where(es_muerto[:3] & con_carga[:3], w_exp, 0.0))
        mf_pd = (
            np.sum(np.where(es_muerto[:3] & con_carga[:3], w_exp * humedad_muerta, 0.0)) / w_exp_sum
            if w_exp_sum > 0 else humedad_muerta
        )
        w_muerto_sum = w_exp_sum
        w_vivo_exp = cargas[3:] * np.exp(-500.0 / np.where(savs[3:] > 0, savs[3:], 1.0))
        w_vivo_sum = np.sum(np.where(con_carga[3:], w_vivo_exp, 0.0))
        razon_w = (w_muerto_sum / w_vivo_sum) if w_vivo_sum > 0 else np.inf
        if np.isinf(razon_w):
            mx_viva = mx_muerta
        else:
            mx_viva = max(2.9 * razon_w * (1 - mf_pd / mx_muerta) - 0.226, mx_muerta)
    else:
        mx_viva = mx_muerta

    # Carga neta (Albini 1976): descuenta el contenido mineral total.
    wn = cargas * (1.0 - _CONTENIDO_MINERAL_TOTAL)
    wn_muerto = np.sum(np.where(es_muerto & con_carga, f * wn, 0.0)) if a_muerto > 0 else 0.0
    wn_vivo = np.sum(np.where(~es_muerto, wn, 0.0))  # sin ponderar (ver nota en fuente R)

    mf_muerto = np.sum(np.where(es_muerto & con_carga, f * humedades, 0.0)) if a_muerto > 0 else 0.0
    mf_vivo = np.sum(np.where(~es_muerto, f * humedades, 0.0)) if a_vivo > 0 else 0.0

    sav_muerto = np.sum(np.where(es_muerto & con_carga, f * savs, 0.0)) if a_muerto > 0 else 0.0
    sav_vivo = np.sum(np.where(~es_muerto, f * savs, 0.0)) if a_vivo > 0 else 0.0
    sav_tot = f_muerto * sav_muerto + f_vivo * sav_vivo
    if sav_tot <= 0:
        return _ResultadoBase(0.0, 0.0, beta, 1.0)

    h_muerto = _HEAT_CONTENT_BTU_LB
    h_vivo = _HEAT_CONTENT_BTU_LB

    def _amortiguacion(mf, mx):
        if mx <= 0:
            return 0.0
        r = mf / mx
        if r >= 1.0:
            return 0.0
        return max(1 - 2.59 * r + 5.11 * r ** 2 - 3.52 * r ** 3, 0.0)

    nm_muerto = _amortiguacion(mf_muerto, mx_muerta) if hay_muerto else 0.0
    nm_vivo = _amortiguacion(mf_vivo, mx_viva) if hay_vivo else 0.0

    beta_op = 3.348 * sav_tot ** (-0.8189)
    rpr = beta / beta_op if beta_op > 0 else 0.0

    gamma_max = (sav_tot ** 1.5) / (495.0 + 0.0594 * sav_tot ** 1.5)
    a_exp = 133.0 * sav_tot ** (-0.7913)

    suma_muerto = wn_muerto * h_muerto * nm_muerto * _NS
    suma_vivo = wn_vivo * h_vivo * nm_vivo * _NS
    ir = gamma_max * (rpr * np.exp(1 - rpr)) ** a_exp * (suma_muerto + suma_vivo)  # BTU/ft^2/min

    xi = (192.0 + 0.2595 * sav_tot) ** (-1) * np.exp((0.792 + 0.681 * sav_tot ** 0.5) * (beta + 0.1))

    # --- Coeficiente de viento (velocidad a altura de llama media) ---
    viento_10m_ms = clima.get("viento_velocidad", 3.0)
    viento_mph = viento_10m_ms * 2.23694 * modelo.reduccion_viento
    u_ft_min = viento_mph * 88.0

    c = 7.47 * np.exp(-0.133 * sav_tot ** 0.55)
    b_exp = 0.02526 * sav_tot ** 0.54
    e_exp = 0.715 * np.exp(-3.59e-4 * sav_tot)
    phi_w = c * u_ft_min ** b_exp * (rpr ** (-e_exp) if rpr > 0 else 0.0)

    # --- Sumidero de calor ---
    rho_b = np.sum(cargas) / delta if delta > 0 else 0.0
    qig = 250.0 + 1116.0 * humedades
    eps_muerto = (
        np.sum(np.where(es_muerto & con_carga, f * qig * np.exp(-138.0 / np.where(savs > 0, savs, 1.0)), 0.0))
        if a_muerto > 0 else 0.0
    )
    eps_vivo = (
        np.sum(np.where(~es_muerto, f * qig * np.exp(-138.0 / np.where(savs > 0, savs, 1.0)), 0.0))
        if a_vivo > 0 else 0.0
    )
    eps = f_muerto * eps_muerto + f_vivo * eps_vivo
    sumidero = rho_b * eps
    if sumidero <= 0:
        return _ResultadoBase(0.0, float(phi_w), beta, 1.0)

    r0_ft_min = (ir * xi) / sumidero  # (1 + phi_w + phi_s) se aplica después, por dirección
    r0_m_min = r0_ft_min * 0.3048

    tiempo_residencia_min = 384.0 / sav_tot if sav_tot > 0 else 1.0

    return _ResultadoBase(float(r0_m_min), float(phi_w), float(beta), float(tiempo_residencia_min))


def razon_largo_ancho(modelo: ModeloCombustible, clima: dict) -> float:
    """
    Razón largo/ancho (LWR) de la elipse de propagación, en función de la
    velocidad de viento efectiva a altura de llama media (Anderson 1983).
    """
    viento_10m_ms = clima.get("viento_velocidad", 3.0)
    viento_mph = viento_10m_ms * 2.23694 * modelo.reduccion_viento
    lwr = 0.936 * np.exp(0.2566 * viento_mph) + 0.461 * np.exp(-0.1548 * viento_mph) - 0.397
    return float(np.clip(lwr, 1.0, 8.0))


def velocidad_direccional(
    base: _ResultadoBase,
    lwr: float,
    viento_direccion_deg: float,
    pendiente_fraccion: np.ndarray,
    angulo_direccion_deg: float,
) -> np.ndarray:
    """
    Velocidad de propagación (m/min) hacia una dirección dada, para toda
    la grilla (pendiente_fraccion es un array filas x columnas con la
    pendiente -- tan(theta) -- en esa dirección para cada celda).

    `base` (de `velocidad_base`) y `lwr` (de `razon_largo_ancho`) se
    calculan UNA vez por paso por modelo de combustible (no dependen de
    la dirección ni de la celda) y se reusan para las 8 direcciones, para
    no repetir el cálculo escalar de Rothermel ocho veces por nada.

    Combina, como en la fórmula original de Rothermel R = R0*xi*(1+phi_w+phi_s):
      - phi_w efectivo: se redistribuye angularmente con la elipse de
        Anderson (1983) en vez de aplicarse solo en la dirección del
        viento, de forma autoconsistente con R_cabeza y R_reverso
        (R_reverso = R_cabeza*(1-e)/(1+e), relación estándar en literatura).
      - phi_s: coeficiente de pendiente de Rothermel, evaluado con la
        pendiente real de esta dirección (no depende del viento).
    """
    if base.r0_m_min <= 0.0:
        return np.zeros_like(pendiente_fraccion)

    excentricidad = np.sqrt(max(1.0 - 1.0 / (lwr ** 2), 0.0))
    theta = np.radians(viento_direccion_deg - angulo_direccion_deg)

    if excentricidad > 0:
        denominador = 1.0 - excentricidad * np.cos(theta)
        denominador = denominador if denominador > 1e-6 else 1e-6
        forma_viento = (1.0 + base.phi_viento) * (1.0 - excentricidad) / denominador
    else:
        forma_viento = 1.0 + base.phi_viento
    phi_viento_efectivo = forma_viento - 1.0

    # Coeficiente de pendiente de Rothermel (1972): fs = 5.275 * beta^-0.3 * slope^2.
    beta = base.beta if base.beta > 0 else 1e-6
    phi_pendiente = 5.275 * beta ** (-0.3) * np.square(pendiente_fraccion)

    r_direccion = base.r0_m_min * (1.0 + phi_viento_efectivo + phi_pendiente)
    return np.clip(r_direccion, 0.0, None)


def _sav_caracteristico(modelo: ModeloCombustible) -> float:
    """SAV característico (ponderado por área superficial), igual que en
    `velocidad_base` pero sin depender del clima -- lo necesita tanto el
    cálculo de velocidad como el de tiempo de residencia."""
    cargas, savs = _componentes(modelo)
    es_muerto = np.array([True, True, True, False, False])
    con_carga = cargas > 0.0

    a = savs * cargas / _RHO_PARTICULA
    a_muerto = np.sum(np.where(es_muerto & con_carga, a, 0.0))
    a_vivo = np.sum(np.where(~es_muerto & con_carga, a, 0.0))
    a_tot = a_muerto + a_vivo
    if a_tot <= 0:
        return 0.0

    f = np.zeros(5)
    if a_muerto > 0:
        f[:3] = np.where(con_carga[:3], a[:3] / a_muerto, 0.0)
    if a_vivo > 0:
        f[3:] = np.where(con_carga[3:], a[3:] / a_vivo, 0.0)

    f_muerto, f_vivo = a_muerto / a_tot, a_vivo / a_tot
    sav_muerto = np.sum(f[:3] * savs[:3])
    sav_vivo = np.sum(f[3:] * savs[3:])
    return float(f_muerto * sav_muerto + f_vivo * sav_vivo)


def pasos_combustion(modelo: ModeloCombustible, minutos_por_paso: int) -> int:
    """Duración de la combustión activa, en número de pasos, a partir del
    tiempo de residencia de llama de Anderson (1969) (tr = 384/sigma, con
    sigma el SAV característico del modelo). Con un piso de 1 paso para
    que la celda sea visible al menos un frame."""
    sav_tot = _sav_caracteristico(modelo)
    if sav_tot <= 0:
        return 1
    tr_min = 384.0 / sav_tot
    return max(1, round(tr_min / minutos_por_paso))
