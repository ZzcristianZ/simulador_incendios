# Simulador de incendios preciso — Plan de implementación por fases

> **Para agentes:** SUB-SKILL REQUERIDA: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Objetivo:** Convertir el simulador en una herramienta que responda con precisión medible la pregunta del proyecto: *¿Cómo influyen los cambios en los parámetros ambientales y del terreno sobre la velocidad de propagación y el área afectada por un incendio forestal a lo largo del tiempo?*

**Arquitectura:** Se conserva la física de Rothermel (1972) y la elipse de Anderson (1983), pero (1) viento y pendiente se combinan como vectores en una sola elipse por celda (Finney 1998, método de FARSITE); (2) el autómata probabilístico de 8 vecinos se reemplaza por un frente de **conjuntos de nivel** (level set) que avanza con la función soporte de esa elipse, sin sesgo de dirección ni saturación; (3) se corrigen la métrica de velocidad, la convención del viento y la rasterización de vías; (4) se agrega un laboratorio de sensibilidad que varía un parámetro a la vez y exporta curvas de velocidad y área en el tiempo. La API pública de `SimuladorIncendio` no cambia, así que `app.py` y `main_prueba.py` siguen funcionando.

**Stack:** Python 3.14, numpy, scipy, matplotlib, Streamlit. Pruebas con `unittest` de la librería estándar (no se agrega pytest).

**Spec:** Pregunta de estudio definitiva (título asignado por el docente) + hallazgos verificados en la sección *Contexto*. Documento del parcial: `Downloads/Simulador_Incendios_Primer_Parcial_Viabilidad.docx` (no se modifica en este plan).

## Contexto: qué está mal hoy y por qué este diseño

Todo lo siguiente se verificó ejecutando el código actual (no de memoria):

| # | Hallazgo | Evidencia | Efecto en la pregunta de estudio |
|---|---|---|---|
| 1 | En pasto la probabilidad por celda se satura en 1 (`R·15/10 ≥ 1` con R ≥ 0.67 m/min) | Viento 0, 3 y 6 m/s dan **exactamente** la misma área (crece como (2·paso+1)² celdas) | El viento no tiene ningún efecto: la variable central de la pregunta queda muda |
| 2 | Cada celda recibe una tirada independiente por cada vecino en llamas | En bosque el radio simulado es ~2× el de Rothermel | Velocidades y áreas infladas |
| 3 | `velocidad_m_min = √área / tiempo` no es una velocidad | En un círculo infla el radio 1.77× | La métrica reportada no es la velocidad de propagación |
| 4 | Convención del viento rotada 90° | Viento del oeste (270°) empuja el fuego al **sur** | Dirección de avance equivocada |
| 5 | `phi_pendiente` eleva la pendiente al cuadrado sin signo | Bajada de 30% da 0.6764 m/min, igual que la subida | Cuesta abajo el fuego se acelera (debería retroceder más lento) |
| 6 | Las vías se rasterizan solo en sus vértices | Vías como puntos sueltos en el mapa | Los cortafuegos reales tienen huecos |
| 7 | Cualquier método de vecindad fija recorta los flancos | Área perdida vs. la elipse analítica: 8 vecinos −31% (LWR 1.8) / −81% (LWR 8); 16 vecinos −12% / −68%; 176 vecinos −0.4% / −18% | Con viento, el área se subestima justo cuando la pregunta mide el efecto del viento |

**Prototipo validado** (en el scratchpad de la sesión que escribió este plan): todo el código de este plan se ejecutó antes de escribirlo. Resultados del motor de conjuntos de nivel contra la elipse analítica de Anderson: círculo −0.8% de área; LWR 1.8 −2.1%; LWR 3.5 +4.7%; velocidad de cabeza con error ≤ 2%. Límite conocido: LWR 8 (pasto con viento > ~9 m/s) sobreestima el área de los flancos (+36%); la app lo avisa. 46 pruebas pasan en ~17 s; el barrido completo de sensibilidad corre en ~26 s.

**Hallazgos preliminares del barrido (para la discusión del informe):** la temperatura casi no mueve el fuego (en Rothermel solo actúa vía humedad del combustible); con viento suave (2 m/s) el área no aumenta aunque la cabeza se acelere (la elipse de Anderson se alarga más rápido de lo que Rothermel acelera la cabeza: propiedad conocida de la combinación estándar BehavePlus/FARSITE); el pasto sale de una grilla de 2 km en 2 h.

## Restricciones globales

- Identificadores, docstrings y comentarios en español (convención del repo, `CLAUDE.md`).
- Sin dependencias nuevas. Pruebas con `unittest`: `python -B -m unittest discover -s tests -t . -v` (`-B` evita reescribir los `.pyc`, que están versionados).
- La API pública de `SimuladorIncendio` se conserva: constructor `(filas, columnas, tam_celda_m, grid_inicial, elevacion)`, `puede_arder`, `iniciar_incendio`, `simular_paso(clima, multiplicador_riesgo)`, `.grid`, `.paso_actual`, y las constantes `ESTADO_*`.
- `CLAUDE.md` exige **confirmación explícita del usuario** antes de cambiar fórmulas o constantes de `modelo_rothermel.py`: las Tareas 2, 3 y 5 tienen un paso de checkpoint que se detiene a pedirla.
- Ninguna prueba usa red (nada de Nominatim, Overpass ni Open-Meteo).
- `TAM_CELDA_M = 10` y `MINUTOS_POR_PASO = 15` no cambian en la app.
- Cada commit termina con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. El commit de línea base de la Tarea 1 incluye cambios de sesiones anteriores y requiere aprobación del usuario.
- No se modifica el documento del parcial (.docx) en este plan.

## Foco de revisión

Entradas que ninguna prueba "del camino feliz" cubre y que más probablemente muerden a quien use el simulador:

1. **El fuego llega al borde de la grilla** → el área deja de crecer y la curva se aplana en silencio. Esperado: el laboratorio marca `toca_borde` y la app avisa. Pruebas: `test_marca_cuando_el_fuego_toca_el_borde` (Tarea 9); aviso en la app (Tarea 6).
2. **Origen sin combustible (agua/vía) o combustible demasiado húmedo** → no debe colgarse ni inventar área. Pruebas: `test_origen_en_agua_no_propaga_ni_se_cuelga`, `test_combustible_demasiado_humedo_no_propaga` (Tarea 5); `test_si_no_puede_arder_el_area_es_cero` (Tarea 9).
3. **Lluvia a mitad de la corrida** (modo tiempo real, clima por hora) → el frente se pausa y luego reanuda. Prueba: `test_la_lluvia_pausa_el_avance` (Tarea 5).
4. **Viento que cambia de dirección entre pasos, o que llega como 0°/360°** → el frente gira de forma coherente. Pruebas: `test_el_frente_gira_si_el_viento_cambia`, `test_la_direccion_360_equivale_a_0` (Tarea 5).
5. **Terreno real irregular** (elevación interpolada, bordes) → sin NaN ni velocidades absurdas. Prueba: `test_terreno_irregular_no_produce_nan` (Tarea 5).

## Mapa de archivos

| Archivo | Cambio | Responsabilidad |
|---|---|---|
| `modelo_rothermel.py` | Modificar | Humedad por clase y combustible vivo configurable; elipse efectiva viento + pendiente; se eliminan funciones que quedan sin uso |
| `metricas_fuego.py` | Modificar | Velocidad de cabeza desde el punto de ignición |
| `simulador_automata.py` | Reescribir | Frente de conjuntos de nivel (misma API pública) |
| `ingesta_geografica.py` | Modificar | Vías rasterizadas como líneas continuas |
| `entorno_simulacion.py` | Modificar | `terreno_controlado` para experimentos |
| `experimentos.py` | Crear | Laboratorio de sensibilidad (CSV + gráficas) |
| `app.py`, `main_prueba.py` | Modificar | Origen para la métrica, etiquetas, humedad viva manual, avisos |
| `tests/` | Crear | `test_rothermel.py`, `test_metricas.py`, `test_motor.py`, `test_terreno.py`, `test_experimentos.py` |
| `README.md`, `CLAUDE.md`, `.claude/commands/*.md` | Modificar | Documentación del motor, comandos de prueba y de experimentos, resultados |

## Fases y esfuerzo estimado

| Fase | Tareas | Esfuerzo aprox. |
|---|---|---|
| 0. Línea base y red de seguridad | 1 | ½ día |
| 1. Física (con checkpoint) | 2, 3 | 1 día |
| 2. Métrica de velocidad | 4 | ½ día |
| 3. Motor de conjuntos de nivel | 5, 6 | 2 días |
| 4. Terreno | 7, 8 | ½ día |
| 5. Laboratorio de sensibilidad | 9, 10 | 1–2 días |

---

## Fase 0 — Línea base y red de seguridad

### Tarea 1: Línea base, infraestructura de pruebas y caracterización de Rothermel

**Archivos:**
- Crear: `tests/__init__.py` (vacío), `tests/test_rothermel.py`
- Modificar: `CLAUDE.md`, `.claude/commands/build-check.md`, `.claude/commands/refactor.md`

**Interfaces:**
- Consume: `modelo_rothermel.velocidad_base(modelo, clima)`, `razon_largo_ancho(modelo, clima)`, `FUEL_MODEL_LIGERO`, `FUEL_MODEL_DENSO` (existentes).
- Produce: helper `clima(t, hr, v=0.0, direccion=0.0, **extra)` en `tests/test_rothermel.py`, que reusan las Tareas 2 y 3.

- [ ] **Paso 1: Línea base de git (requiere aprobación del usuario).** Hay cambios sin commitear de sesiones anteriores (`README.md`, `app.py`, `main_prueba.py`, `simulador_automata.py`, `CLAUDE.md`, `.claude/`). Mostrar `git status` al usuario y pedir permiso para commitearlos. Si lo aprueba:

```bash
git add README.md app.py main_prueba.py simulador_automata.py CLAUDE.md .claude/settings.json .claude/hooks .claude/commands docs/superpowers/plans
git commit -m "$(cat <<'EOF'
chore: línea base antes del motor de conjuntos de nivel

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
git checkout -b motor-conjuntos-nivel
```

Si no lo aprueba, trabajar sobre `git stash` o detenerse y preguntar cómo seguir.

- [ ] **Paso 2: Escribir las pruebas de caracterización.** Fijan los valores del modelo ya verificado para detectar cualquier cambio accidental en la física. Crear `tests/__init__.py` vacío y `tests/test_rothermel.py`:

```python
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
```

(`numpy` y `contenido_humedad_equilibrio` se importan ya porque las Tareas 2 y 3 agregan clases a este mismo archivo.)

- [ ] **Paso 3: Ejecutar.** Son pruebas de *caracterización*: fijan el comportamiento actual, así que deben pasar de inmediato (no hay fase roja).

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 6 tests ... OK`

- [ ] **Paso 4: Actualizar la documentación de comandos.** En `CLAUDE.md`, reemplazar:

```markdown
- No hay suite de pruebas automatizada. Lo más cercano a un "test" en este
  repo es la verificación de sintaxis:
  `python -m py_compile app.py simulador_automata.py main_prueba.py modelo_rothermel.py modelo_probabilidad.py entorno_simulacion.py ingesta_clima.py ingesta_geografica.py metricas_fuego.py`
```

por:

```markdown
- Pruebas (stdlib, sin pytest; `-B` evita reescribir los `.pyc` versionados):
  `python -B -m unittest discover -s tests -t . -v`
- Verificación rápida de sintaxis:
  `python -m py_compile app.py simulador_automata.py main_prueba.py modelo_rothermel.py modelo_probabilidad.py entorno_simulacion.py ingesta_clima.py ingesta_geografica.py metricas_fuego.py`
```

En `.claude/commands/build-check.md`, reemplazar el punto 3 (desde `3. **Pruebas: no hay suite automatizada.**` hasta el comando `py_compile` inclusive) por:

```markdown
3. Pruebas: `python -B -m unittest discover -s tests -t . -v`
```

En `.claude/commands/refactor.md`, reemplazar el último párrafo por:

```markdown
Después de refactorizar, corré las pruebas del proyecto:
`python -B -m unittest discover -s tests -t . -v`.
```

- [ ] **Paso 5: Commit**

```bash
git add tests/__init__.py tests/test_rothermel.py CLAUDE.md .claude/commands/build-check.md .claude/commands/refactor.md
git commit -m "$(cat <<'EOF'
test: caracterización del modelo de Rothermel y comando de pruebas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 1 — Física (checkpoint obligatorio)

### Tarea 2: Humedad del combustible por clase y combustible vivo configurable

**Archivos:**
- Modificar: `modelo_rothermel.py` (`velocidad_base`)
- Test: `tests/test_rothermel.py` (agregar clase)

**Interfaces:**
- Consume: `contenido_humedad_equilibrio(temp_c, hum_rel)` de `modelo_probabilidad`.
- Produce: `velocidad_base(modelo, clima, humedades_muertas=None) -> _ResultadoBase`. `humedades_muertas` es una tupla `(1h, 10h, 100h)` en %; `None` = EMC del clima en las tres (comportamiento actual). `clima["humedad_combustible_vivo"]` (%) reemplaza la constante estacional si viene. La Tarea 5 pasa las humedades con tiempo de respuesta; la Tarea 6 expone el combustible vivo en la app.

- [ ] **Paso 1: CHECKPOINT.** Mostrar al usuario el cambio propuesto (Pasos 4–5) y esperar su confirmación explícita (regla de `CLAUDE.md`). Explicarle: sin humedades explícitas el resultado es idéntico al actual (lo garantiza la prueba de caracterización); el cambio permite que 10h/100h respondan más lento que 1h (Tarea 5) y que la humedad del combustible vivo sea una variable experimental.

- [ ] **Paso 2: Escribir las pruebas que fallan.** Agregar al final de `tests/test_rothermel.py`, antes del bloque `if __name__`:

```python
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
```

- [ ] **Paso 3: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_rothermel.HumedadDeCombustible -v`
Expected: 3 ERROR con `TypeError: velocidad_base() takes 2 positional arguments but 3 were given` y 1 FAIL en `test_combustible_vivo_mas_seco_propaga_mas_rapido` (la clave se ignora hoy).

- [ ] **Paso 4: Implementar.** En `modelo_rothermel.py`, reemplazar el encabezado de `velocidad_base` y el cálculo de humedades:

```python
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
```

por:

```python
def velocidad_base(modelo: ModeloCombustible, clima: dict, humedades_muertas=None) -> _ResultadoBase:
    """
    Velocidad de propagación en llano (sin pendiente) en la dirección del
    viento, más el coeficiente de viento y el packing ratio (necesario
    para el coeficiente de pendiente). Se calcula UNA vez por paso por
    modelo de combustible (el clima es uniforme sobre la grilla), no por
    celda -- igual que el resto del proyecto.

    humedades_muertas: (1h, 10h, 100h) en %. Si es None, las tres clases
    toman la humedad de equilibrio (EMC) del clima del paso. La humedad del
    combustible vivo sale de clima["humedad_combustible_vivo"] (%) o, si no
    viene, de la constante estacional del modelo.
    """
    cargas, savs = _componentes(modelo)
    delta = modelo.profundidad_ft

    es_muerto = np.array([True, True, True, False, False])
    con_carga = cargas > 0.0

    if humedades_muertas is None:
        emc = contenido_humedad_equilibrio(clima.get("temperatura", 25.0), clima.get("humedad_relativa", 50.0))
        humedades_muertas = (emc, emc, emc)
    humedad_viva = clima.get("humedad_combustible_vivo", modelo.humedad_viva_estacional)
    humedades = np.array([*humedades_muertas, humedad_viva, humedad_viva], dtype=float) / 100.0
```

- [ ] **Paso 5: Implementar (humedad fina muerta ponderada por clase).** En el mismo archivo, reemplazar:

```python
        mf_pd = (
            np.sum(np.where(es_muerto[:3] & con_carga[:3], w_exp * humedad_muerta, 0.0)) / w_exp_sum
            if w_exp_sum > 0 else humedad_muerta
        )
```

por:

```python
        mf_pd = (
            np.sum(np.where(es_muerto[:3] & con_carga[:3], w_exp * humedades[:3], 0.0)) / w_exp_sum
            if w_exp_sum > 0 else humedades[0]
        )
```

- [ ] **Paso 6: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 10 tests ... OK` (la caracterización sigue pasando: sin humedades explícitas nada cambia).

- [ ] **Paso 7: Commit**

```bash
git add modelo_rothermel.py tests/test_rothermel.py
git commit -m "$(cat <<'EOF'
feat: humedad de combustible muerto por clase y combustible vivo configurable

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

### Tarea 3: Elipse efectiva con viento y pendiente combinados como vectores

**Archivos:**
- Modificar: `modelo_rothermel.py` (`_ResultadoBase`, retorno de `velocidad_base`, `razon_largo_ancho`; nueva `elipse_efectiva`)
- Test: `tests/test_rothermel.py` (agregar clase)

**Interfaces:**
- Consume: `velocidad_base` (Tarea 2).
- Produce: `elipse_efectiva(base, viento_hacia_deg, pendiente_tan, azimut_subida_deg) -> (r_cabeza, r_cola, lwr, azimut_cabeza)`: arrays numpy del tamaño de `pendiente_tan`, velocidades en m/min, azimut en grados (0 = norte, 90 = este). `viento_hacia_deg` es hacia DÓNDE sopla el viento (no de dónde viene). La Tarea 5 la usa para cada tipo de combustible.

- [ ] **Paso 1: CHECKPOINT.** Mostrar al usuario el cambio (Pasos 4–6) y esperar su confirmación explícita. Explicarle: hoy viento y pendiente se suman por dirección y, por un error de signo, una bajada acelera el fuego igual que una subida (0.6764 m/min en ambos casos). El método de FARSITE (Finney 1998) los combina como vectores en una sola elipse; cuesta arriba la velocidad no cambia (0.6764) y cuesta abajo el fuego retrocede más lento que en llano (0.142 contra 0.260 m/min). Es la mejora que el README ya listaba como "extensión futura".

- [ ] **Paso 2: Escribir las pruebas que fallan.** Agregar a `tests/test_rothermel.py`, antes de `class HumedadDeCombustible`:

```python
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
```

- [ ] **Paso 3: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_rothermel.ElipseEfectiva -v`
Expected: 7 ERROR con `AttributeError: module 'modelo_rothermel' has no attribute 'elipse_efectiva'`.

- [ ] **Paso 4: Guardar los coeficientes de la función de viento.** En `modelo_rothermel.py`, reemplazar la dataclass `_ResultadoBase` por:

```python
@dataclass(frozen=True)
class _ResultadoBase:
    r0_m_min: float       # velocidad en llano, sin viento (m/min)
    phi_viento: float     # coeficiente de viento de Rothermel (adimensional)
    beta: float           # packing ratio (para el coeficiente de pendiente)
    tiempo_residencia_min: float
    # phi_viento = c_viento * U^b_viento * rpr^(-e_viento), con U en ft/min a
    # altura de llama media: se guardan para poder invertirla (viento efectivo).
    c_viento: float = 0.0
    b_viento: float = 1.0
    e_viento: float = 0.0
    rpr: float = 0.0
```

y el último `return` de `velocidad_base`:

```python
    return _ResultadoBase(float(r0_m_min), float(phi_w), float(beta), float(tiempo_residencia_min))
```

por:

```python
    return _ResultadoBase(float(r0_m_min), float(phi_w), float(beta), float(tiempo_residencia_min),
                          float(c), float(b_exp), float(e_exp), float(rpr))
```

- [ ] **Paso 5: Implementar `elipse_efectiva`.** Reemplazar la función `razon_largo_ancho` completa por (dejar `velocidad_direccional` y lo que sigue intactos; la Tarea 5 los elimina):

```python
def _lwr_anderson(viento_llama_mph):
    """Razón largo/ancho (LWR) de Anderson (1983) para un viento a altura
    de llama media (mph), acotada a [1, 8] como en FARSITE/BehavePlus."""
    lwr = 0.936 * np.exp(0.2566 * viento_llama_mph) + 0.461 * np.exp(-0.1548 * viento_llama_mph) - 0.397
    return np.clip(lwr, 1.0, 8.0)


def razon_largo_ancho(modelo: ModeloCombustible, clima: dict) -> float:
    """
    Razón largo/ancho (LWR) de la elipse de propagación, en función de la
    velocidad de viento efectiva a altura de llama media (Anderson 1983).
    """
    viento_10m_ms = clima.get("viento_velocidad", 3.0)
    return float(_lwr_anderson(viento_10m_ms * 2.23694 * modelo.reduccion_viento))


def elipse_efectiva(base: _ResultadoBase, viento_hacia_deg: float,
                    pendiente_tan: np.ndarray, azimut_subida_deg: np.ndarray):
    """
    Elipse de propagación de cada celda con viento y pendiente combinados
    como VECTORES (Finney 1998, FARSITE; ver también Andrews 2018):
    phi_w apunta hacia donde sopla el viento y phi_s cuesta arriba; su
    resultante phi_e da la velocidad de cabeza R = R0 (1 + phi_e) y su
    dirección. La forma (LWR) sale del "viento efectivo": el viento que por
    sí solo produciría phi_e, invirtiendo la función de viento de Rothermel.

    pendiente_tan y azimut_subida_deg son arrays (una pendiente por celda).
    Devuelve arrays (r_cabeza, r_cola, lwr, azimut_cabeza) en m/min y grados
    (0 = norte, 90 = este).
    """
    ceros = np.zeros_like(pendiente_tan, dtype=float)
    if base.r0_m_min <= 0.0:
        return ceros, ceros, ceros + 1.0, ceros

    phi_s = 5.275 * max(base.beta, 1e-6) ** (-0.3) * np.square(pendiente_tan)
    aw, au = np.radians(viento_hacia_deg), np.radians(azimut_subida_deg)
    este = base.phi_viento * np.sin(aw) + phi_s * np.sin(au)
    norte = base.phi_viento * np.cos(aw) + phi_s * np.cos(au)
    phi_e = np.hypot(este, norte)
    azimut_cabeza = np.degrees(np.arctan2(este, norte)) % 360.0

    divisor = base.c_viento * base.rpr ** (-base.e_viento) if base.c_viento > 0 and base.rpr > 0 else 0.0
    viento_efectivo_ft_min = (phi_e / divisor) ** (1.0 / base.b_viento) if divisor > 0 else ceros
    lwr = _lwr_anderson(viento_efectivo_ft_min / 88.0)

    excentricidad = np.sqrt(1.0 - 1.0 / np.square(lwr))
    r_cabeza = base.r0_m_min * (1.0 + phi_e)
    r_cola = r_cabeza * (1.0 - excentricidad) / (1.0 + excentricidad)
    return r_cabeza, r_cola, lwr, azimut_cabeza
```

- [ ] **Paso 6: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 17 tests ... OK`

- [ ] **Paso 7: Commit**

```bash
git add modelo_rothermel.py tests/test_rothermel.py
git commit -m "$(cat <<'EOF'
feat: elipse efectiva con viento y pendiente combinados como vectores (Finney 1998)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 2 — Métrica de velocidad

### Tarea 4: Velocidad de cabeza desde el punto de ignición

**Archivos:**
- Modificar: `metricas_fuego.py`, `app.py`, `main_prueba.py`
- Crear: `tests/test_metricas.py`

**Interfaces:**
- Produce: `CalculadorMetricas(tam_celda_m=10, minutos_por_paso=15, origen=None)`. Con `origen=(fila, col)`, `velocidad_m_min` = distancia del origen a la celda afectada más lejana / tiempo. Sin origen = radio del círculo de igual área / tiempo. La clave `velocidad_m_min` del reporte no cambia de nombre.

- [ ] **Paso 1: Escribir las pruebas que fallan.** Crear `tests/test_metricas.py`:

```python
import unittest

import numpy as np

from metricas_fuego import CalculadorMetricas
from simulador_automata import ESTADO_VEGETACION_LIGERA, ESTADO_QUEMADO, ESTADO_FUEGO


class VelocidadDePropagacion(unittest.TestCase):
    def setUp(self):
        self.inicial = np.full((21, 21), ESTADO_VEGETACION_LIGERA, dtype=int)
        self.actual = self.inicial.copy()
        self.actual[10, 10:21] = ESTADO_QUEMADO  # el frente avanzó 10 celdas al este
        self.actual[10, 20] = ESTADO_FUEGO

    def test_con_origen_mide_la_distancia_de_cabeza(self):
        rep = CalculadorMetricas(10, 15, origen=(10, 10)).generar_reporte(self.inicial, self.actual, 1)
        self.assertAlmostEqual(rep["velocidad_m_min"], 100.0 / 15, places=2)

    def test_sin_origen_usa_el_radio_equivalente(self):
        rep = CalculadorMetricas(10, 15).generar_reporte(self.inicial, self.actual, 1)
        self.assertAlmostEqual(rep["velocidad_m_min"], np.sqrt(11 * 100.0 / np.pi) / 15, places=2)

    def test_en_el_paso_cero_la_velocidad_es_cero(self):
        rep = CalculadorMetricas(10, 15, origen=(10, 10)).generar_reporte(self.inicial, self.actual, 0)
        self.assertEqual(rep["velocidad_m_min"], 0.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Paso 2: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_metricas -v`
Expected: 2 ERROR con `TypeError: CalculadorMetricas.__init__() got an unexpected keyword argument 'origen'` y 1 FAIL en `test_sin_origen_usa_el_radio_equivalente` (hoy da √1100/15 = 2.21 en vez de 1.25).

- [ ] **Paso 3: Implementar.** En `metricas_fuego.py`, reemplazar el constructor:

```python
    def __init__(self, tam_celda_m: int = 10, minutos_por_paso: int = 15):
        self.tam_celda_m = tam_celda_m
        self.area_celda_m2 = tam_celda_m ** 2
        self.minutos_por_paso = minutos_por_paso
```

por:

```python
    def __init__(self, tam_celda_m: int = 10, minutos_por_paso: int = 15, origen=None):
        """origen: (fila, col) del punto de ignición, para medir la
        velocidad de cabeza. Sin origen se reporta la velocidad radial
        equivalente (radio del círculo de igual área / tiempo)."""
        self.tam_celda_m = tam_celda_m
        self.area_celda_m2 = tam_celda_m ** 2
        self.minutos_por_paso = minutos_por_paso
        self.origen = origen
```

y el cálculo de velocidad:

```python
        velocidad_avance = (
            np.sqrt(area_afectada_m2) / tiempo_transcurrido_min if tiempo_transcurrido_min > 0 else 0
        )
```

por:

```python
        # Velocidad de cabeza: distancia del origen a la celda afectada más
        # lejana, sobre el tiempo transcurrido. (sqrt(área)/tiempo, lo que se
        # usaba antes, no es una velocidad: en un círculo infla el radio 1.77x.)
        if tiempo_transcurrido_min <= 0 or celdas_afectadas_total == 0:
            velocidad_avance = 0.0
        elif self.origen is not None:
            filas_af, cols_af = np.nonzero(mascara_afectada)
            distancia_m = np.hypot(filas_af - self.origen[0], cols_af - self.origen[1]).max() * self.tam_celda_m
            velocidad_avance = distancia_m / tiempo_transcurrido_min
        else:
            velocidad_avance = np.sqrt(area_afectada_m2 / np.pi) / tiempo_transcurrido_min
```

(`mascara_afectada` ya está definida más arriba en `generar_reporte`.)

- [ ] **Paso 4: Pasar el origen desde la app y la demo.** En `app.py`, reemplazar:

```python
        metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=MINUTOS_POR_PASO)
```

por:

```python
        metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=MINUTOS_POR_PASO,
                                      origen=(fila_origen, col_origen))
```

En `main_prueba.py`, reemplazar:

```python
metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=15)
```

por:

```python
metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=15, origen=(fila_origen, col_origen))
```

- [ ] **Paso 5: Ejecutar todas las pruebas y compilar.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 20 tests ... OK`
Run: `python -m py_compile app.py main_prueba.py metricas_fuego.py`
Expected: sin salida.

- [ ] **Paso 6: Commit**

```bash
git add metricas_fuego.py app.py main_prueba.py tests/test_metricas.py
git commit -m "$(cat <<'EOF'
fix: velocidad de propagación como distancia de cabeza, no sqrt(área)/tiempo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 3 — Motor de conjuntos de nivel

### Tarea 5: Frente de conjuntos de nivel (reemplaza el autómata probabilístico)

**Archivos:**
- Reescribir: `simulador_automata.py`
- Modificar: `modelo_rothermel.py` (eliminar funciones que quedan sin uso; docstring del módulo)
- Crear: `tests/test_motor.py`

**Interfaces:**
- Consume: `velocidad_base(modelo, clima, humedades_muertas)` (Tarea 2), `elipse_efectiva(...)` (Tarea 3), `contenido_humedad_equilibrio`.
- Produce: `SimuladorIncendio(filas, columnas, tam_celda_m, grid_inicial=None, elevacion=None, heterogeneidad=0.0, semilla=None)` con la misma API pública, más los atributos `llegada` (minuto de llegada del frente por celda; `inf` = no llegó), `humedad_muerta` (array `[1h, 10h, 100h]` en %) y `lwr_max` (elongación máxima del último paso). Las Tareas 6 y 9 usan `llegada` y `lwr_max`.

- [ ] **Paso 1: CHECKPOINT.** Este paso elimina de `modelo_rothermel.py` las funciones `velocidad_direccional`, `_sav_caracteristico` y `pasos_combustion`, que el motor nuevo deja sin uso. No cambia ninguna fórmula que siga en uso, pero toca el módulo protegido: pedir confirmación explícita al usuario.

- [ ] **Paso 2: Escribir las pruebas que fallan.** Crear `tests/test_motor.py`:

```python
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
```

- [ ] **Paso 3: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_motor -v`
Expected: múltiples ERROR/FAIL: `AttributeError: 'SimuladorIncendio' object has no attribute 'llegada'`, `TypeError: ... unexpected keyword argument 'heterogeneidad'`, y FAIL en `test_viento_del_oeste_empuja_el_fuego_al_este` (el motor actual empuja al sur).

- [ ] **Paso 4: Reescribir `simulador_automata.py` completo:**

```python
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
        self.lwr_max = float(lwr[self._combustible].max()) if self._combustible.any() else 1.0
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
```

- [ ] **Paso 5: Eliminar de `modelo_rothermel.py` lo que quedó sin uso.** Verificar primero que nada más lo usa:

Run: `git grep -n "velocidad_direccional\|pasos_combustion\|_sav_caracteristico" -- "*.py"`
Expected: solo apariciones dentro de `modelo_rothermel.py`.

Borrar desde `def velocidad_direccional(` hasta el final del archivo (`velocidad_direccional`, `_sav_caracteristico`, `pasos_combustion`). En el docstring del módulo, reemplazar:

```python
Responsabilidad ÚNICA de este módulo: dado un tipo de combustible (modelo
de combustible estándar), el clima del paso y la pendiente local por
dirección, calcular la velocidad de propagación REAL (m/min) del frente de
fuego en cada una de las 8 direcciones de la vecindad de Moore.
```

por:

```python
Responsabilidad ÚNICA de este módulo: dado un tipo de combustible (modelo
de combustible estándar), el clima del paso y la pendiente de cada celda,
calcular la elipse de propagación del frente de fuego: velocidades de
cabeza y de retroceso (m/min), forma (LWR) y dirección.
```

y el ítem:

```python
- Viento y pendiente se combinan de forma aditiva, como en la fórmula
  original de Rothermel (1 + phi_viento + phi_pendiente), en vez de
  combinar vectorialmente dos elipses (viento y pendiente) como hace
  FARSITE -- ese nivel de detalle queda como extensión futura.
```

por:

```python
- Viento y pendiente se combinan como vectores en una sola elipse por
  celda (Finney 1998, como FARSITE); ver `elipse_efectiva`.
```

- [ ] **Paso 6: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 38 tests ... OK` (unos 15 s).

- [ ] **Paso 7: Commit**

```bash
git add simulador_automata.py modelo_rothermel.py tests/test_motor.py
git commit -m "$(cat <<'EOF'
feat: frente de conjuntos de nivel con elipse de Huygens en lugar del autómata probabilístico

Corrige saturación de la probabilidad, composición entre vecinos, sesgo
de dirección de la vecindad fija y convención del viento. Agrega humedad
de combustible con tiempo de respuesta y heterogeneidad opcional.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

### Tarea 6: Integración en la app, avisos y documentación del motor

**Archivos:**
- Modificar: `app.py`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consume: `sim.lwr_max`, `sim.llegada` (Tarea 5); `clima["humedad_combustible_vivo"]` (Tarea 2).

- [ ] **Paso 1: Humedad del combustible vivo en modo manual.** En `app.py`, después de la línea del VPD en `clima_manual_valores`:

```python
            "vpd": cm1.number_input("Déficit de presión de vapor (kPa):", value=1.2, min_value=0.0, step=0.1),
```

agregar:

```python
            "humedad_combustible_vivo": cm2.number_input(
                "Humedad combustible vivo (%):", value=100.0, min_value=30.0, max_value=250.0, step=10.0,
                help="Solo afecta al bosque. 100% es un valor estacional típico; más bajo = vegetación más seca."),
```

- [ ] **Paso 2: Etiquetas.** En `app.py`, reemplazar las tres apariciones de `"Vel. Propagación"` por `"Vel. de cabeza"`, y en el resumen final `velocidad media de avance` por `velocidad de cabeza`. Reemplazar el `st.caption` del encabezado:

```python
st.caption(
    "Autómata celular estocástico alimentado con clima, edificios, agua y "
    "vegetación reales del lugar que ingreses. No es una simulación en "
    "tiempo real: cada paso representa 15 minutos de avance del fuego."
)
```

por:

```python
st.caption(
    "Frente de fuego de Rothermel sobre una grilla (conjuntos de nivel), con "
    "clima, edificios, agua y vegetación reales del lugar que ingreses. Cada "
    "paso representa 15 minutos de avance del fuego."
)
```

- [ ] **Paso 3: Avisos de validez.** En `app.py`, justo después del `st.markdown(...)` del **Resumen final**, agregar (dentro del mismo bloque `else:`):

```python
            if sim.lwr_max > 4.0:
                st.info(
                    f"ℹ️ Con este viento la elipse del incendio es muy alargada (LWR {sim.lwr_max:.1f} > 4): "
                    "el área de los flancos puede estar sobreestimada. Rango validado del modelo: LWR ≤ 4."
                )
            if np.isfinite(sim.llegada[[0, -1], :]).any() or np.isfinite(sim.llegada[:, [0, -1]]).any():
                st.warning(
                    "⚠️ El incendio alcanzó el borde del área simulada: desde ahí el área real sería mayor. "
                    "Aumenta el radio para verlo completo."
                )
```

- [ ] **Paso 4: Compilar.**

Run: `python -m py_compile app.py`
Expected: sin salida.

- [ ] **Paso 5: Verificar en el navegador.** Levantar la app con la configuración existente de `.claude/launch.json` (`simulador-incendios`, puerto 8501) y comprobar:
  1. Modo **tiempo real**, "Ocaña, Colombia", radio 300, 20 pasos: la simulación corre, la grilla y el mapa se actualizan, sin errores en consola ni en el log del servidor.
  2. Modo **condiciones controladas**, 30 °C, 35 % HR, viento 4 m/s desde 270°: el frente avanza hacia el **este** (a la derecha en la grilla).
  3. Mismo escenario con viento 12 m/s: aparece el aviso de LWR > 4.
  4. Radio 150 y 40 pasos con clima seco: aparece el aviso de borde.
  5. 20 °C y 75 % HR en manual: aparece "No se pudo sostener combustión" (sin cambios respecto a hoy).

Tomar captura de (2) como evidencia.

- [ ] **Paso 6: Documentación del motor.** En `README.md`:
  - En la tabla de arquitectura, reemplazar la línea de `simulador_automata.py` por:
    `simulador_automata.py    Frente de fuego por conjuntos de nivel (numpy): combustible, pendiente, viento`
  - En la introducción, reemplazar `mediante un **autómata celular estocástico**` por `mediante un **frente de fuego sobre una grilla (método de conjuntos de nivel)**`, y en la nota de terminología `(autómata celular estocástico)` por `(frente por conjuntos de nivel sobre una grilla)`.
  - En la sección 4, reemplazar el ítem **Forma elíptica por viento** por:

```markdown
- **Viento y pendiente combinados como vectores (Finney 1998):** el
  coeficiente de viento de Rothermel apunta hacia donde sopla el viento y
  el de pendiente cuesta arriba; su resultante da la velocidad de cabeza y
  su dirección. La forma del incendio (razón largo/ancho de Anderson, 1983)
  sale del *viento efectivo*, el viento que por sí solo produciría ese
  mismo efecto. Cuesta abajo el fuego retrocede más lento que en llano.
```

  - Reemplazar el primer párrafo de la sección 5 (desde `### 5. Autómata celular` hasta antes de `**¿Y si el clima no da`) por:

```markdown
### 5. Propagación del frente: conjuntos de nivel (`simulador_automata.py`)
El frente de fuego es el contorno cero de una función φ sobre la grilla
(φ ≤ 0 = quemado) y avanza en su dirección normal a la velocidad que dicta
la elipse de cada celda: la *función soporte* de la elipse de Rothermel +
Anderson con viento y pendiente vectoriales. Un incendio puntual crece así
exactamente como la elipse, sin el sesgo de los métodos de vecinos fijos
(un autómata de 8 vecinos pierde ~30% del área con viento moderado y hasta
~80% con viento fuerte, porque solo puede avanzar en 8 direcciones).

- Esquema upwind de primer orden (Osher y Sethian, 1988) con paso de tiempo
  adaptativo (el frente avanza como mucho media celda por subpaso).
- φ se reinicializa como distancia con signo en cada subpaso (Sussman,
  Smereka y Osher, 1994; corrección de subcelda de Russo y Smereka, 2000).
- Cada celda registra el minuto de llegada del frente: de ahí salen el área
  y la velocidad de cabeza en cada instante.
- Agua y vías (velocidad 0) funcionan como cortafuegos.
- La humedad del combustible muerto responde al clima con su tiempo de
  respuesta (clases 1h/10h/100h), no al instante.
- Heterogeneidad opcional (factor aleatorio fijo por celda, con semilla)
  para estudios con réplicas; por defecto el modelo es determinista.
- Verificación contra la elipse analítica: círculo −0.8% de área; LWR 1.8
  −2.1%; LWR 3.5 +4.7%; velocidad de cabeza con error ≤ 2%. Rango validado:
  LWR ≤ 4; por encima la app avisa.
```

  - En *Limitaciones conocidas*, reemplazar el primer ítem (el de la grilla raster de 8 vecinos) por:

```markdown
- El frente usa un esquema de conjuntos de nivel de primer orden: con
  elipses muy alargadas (LWR > 4, pasto con viento fuerte) sobreestima el
  área de los flancos (+35% con LWR 8). La app lo avisa; la mejora es un
  esquema de Godunov anisotrópico.
- La temperatura solo actúa a través de la humedad del combustible (EMC),
  así que su efecto directo es pequeño; no se modela el precalentamiento.
- La lluvia pausa el avance pero no moja el combustible.
```

    y eliminar el ítem que empieza con `- Viento y pendiente se combinan de forma aditiva`.
  - En *Referencias del motor de propagación*, agregar:

```markdown
- Finney, M.A. (1998). *FARSITE: Fire Area Simulator—Model Development
  and Evaluation*. USDA Forest Service, RMRS-RP-4 (combinación vectorial de
  viento y pendiente).
- Osher, S. & Sethian, J.A. (1988). Fronts propagating with
  curvature-dependent speed: algorithms based on Hamilton-Jacobi
  formulations. *Journal of Computational Physics*, 79(1), 12–49.
- Sussman, M., Smereka, P. & Osher, S. (1994). A level set approach for
  computing solutions to incompressible two-phase flow. *Journal of
  Computational Physics*, 114(1), 146–159.
- Russo, G. & Smereka, P. (2000). A remark on computing distance
  functions. *Journal of Computational Physics*, 163(1), 51–67.
```

  - En *Posibles extensiones futuras*, eliminar el ítem de combinar viento y pendiente vectorialmente (ya está hecho) y agregar: `- Esquema de Godunov anisotrópico para elipses muy alargadas (LWR > 4).`

- [ ] **Paso 7: `CLAUDE.md`.** En *Convenciones observadas*, agregar:

```markdown
- `simulador_automata.py` es un frente de conjuntos de nivel: el estado es
  `llegada` (minuto de llegada por celda) y `grid` se deriva de ahí. La
  física por celda sale de `modelo_rothermel.elipse_efectiva`. Rango
  validado: LWR ≤ 4.
```

- [ ] **Paso 8: Commit**

```bash
git add app.py README.md CLAUDE.md
git commit -m "$(cat <<'EOF'
feat: app con humedad del combustible vivo, avisos de validez y docs del motor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 4 — Terreno

### Tarea 7: Vías continuas como cortafuegos

**Archivos:**
- Modificar: `ingesta_geografica.py` (`rasterizar_geografia`)
- Crear: `tests/test_terreno.py`

- [ ] **Paso 1: Escribir la prueba que falla.** Crear `tests/test_terreno.py`:

```python
import unittest

import numpy as np

from ingesta_geografica import rasterizar_geografia, _metros_a_grados
from simulador_automata import ESTADO_SIN_COMBUSTIBLE


class ViasContinuas(unittest.TestCase):
    def test_una_via_recta_queda_sin_huecos(self):
        lat, lon = 8.0, -73.0
        _, grados_lon_por_m = _metros_a_grados(lat)
        via = [(lat, lon - 90 * grados_lon_por_m), (lat, lon + 90 * grados_lon_por_m)]
        grid, _ = rasterizar_geografia({"vias": [via]}, lat, lon, 21, 21, 10)
        cols = np.nonzero(grid[10] == ESTADO_SIN_COMBUSTIBLE)[0]
        self.assertGreaterEqual(len(cols), 17)
        self.assertEqual(len(cols), cols.max() - cols.min() + 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Paso 2: Ejecutar y verificar que falla.**

Run: `python -B -m unittest tests.test_terreno -v`
Expected: FAIL `AssertionError: 2 not greater than or equal to 17` (hoy solo se marcan los 2 vértices).

- [ ] **Paso 3: Implementar.** En `ingesta_geografica.py`, reemplazar:

```python
    mascara_vias = np.zeros((filas, columnas), dtype=bool)
    for via in datos_geo.get("vias", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in via]
        for (fila, col) in puntos:
            fi, ci = int(round(fila)), int(round(col))
            if 0 <= fi < filas and 0 <= ci < columnas:
                mascara_vias[fi, ci] = True
```

por:

```python
    # Cada tramo de vía se muestrea a lo largo (no solo en sus vértices):
    # una vía con huecos no funciona como cortafuego.
    mascara_vias = np.zeros((filas, columnas), dtype=bool)
    for via in datos_geo.get("vias", []):
        puntos = [latlon_a_celda(p_lat, p_lon) for p_lat, p_lon in via]
        for (f0, c0), (f1, c1) in zip(puntos, puntos[1:]):
            n = int(np.ceil(2 * max(abs(f1 - f0), abs(c1 - c0)))) + 1  # cada media celda
            for fila, col in zip(np.linspace(f0, f1, n), np.linspace(c0, c1, n)):
                fi, ci = int(round(fila)), int(round(col))
                if 0 <= fi < filas and 0 <= ci < columnas:
                    mascara_vias[fi, ci] = True
```

(Se muestrea cada media celda porque `round` de Python redondea `.5` al par: con pasos de una celda exacta quedarían huecos alternados.)

- [ ] **Paso 4: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 39 tests ... OK`

- [ ] **Paso 5: Commit**

```bash
git add ingesta_geografica.py tests/test_terreno.py
git commit -m "$(cat <<'EOF'
fix: rasterizar las vías como líneas continuas para que funcionen como cortafuego

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

### Tarea 8: Terreno controlado para experimentos

**Archivos:**
- Modificar: `entorno_simulacion.py`
- Test: `tests/test_terreno.py` (agregar clase)

**Interfaces:**
- Produce: `terreno_controlado(filas, columnas, tam_celda_m, pendiente_pct=0.0, azimut_subida=90.0, estado=ESTADO_VEGETACION_DENSA) -> dict`, con las mismas claves que `preparar_terreno`: `filas`, `columnas`, `grid`, `celda_origen` (centro), `elevacion` (`None` si la pendiente es 0), `datos_geo` (`None`), `geografia_real` (`False`). La usa la Tarea 9.

- [ ] **Paso 1: Escribir las pruebas que fallan.** En `tests/test_terreno.py`, agregar el import `from entorno_simulacion import terreno_controlado` y, antes del bloque `if __name__`:

```python
class TerrenoControlado(unittest.TestCase):
    def test_plano_que_sube_al_este(self):
        t = terreno_controlado(11, 11, 10.0, pendiente_pct=20.0, azimut_subida=90.0)
        self.assertAlmostEqual(t["elevacion"][5, 6] - t["elevacion"][5, 5], 2.0)
        self.assertAlmostEqual(t["elevacion"][4, 5] - t["elevacion"][5, 5], 0.0)
        self.assertEqual(t["celda_origen"], (5, 5))

    def test_sin_pendiente_no_hay_elevacion(self):
        self.assertIsNone(terreno_controlado(11, 11, 10.0)["elevacion"])
```

- [ ] **Paso 2: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_terreno -v`
Expected: ERROR `ImportError: cannot import name 'terreno_controlado' from 'entorno_simulacion'`.

- [ ] **Paso 3: Implementar.** En `entorno_simulacion.py`, agregar después del bloque `from ingesta_geografica import (...)`:

```python
from simulador_automata import ESTADO_VEGETACION_DENSA
```

y antes de `def construir_clima_manual(`:

```python
def terreno_controlado(filas: int, columnas: int, tam_celda_m: float, pendiente_pct: float = 0.0,
                       azimut_subida: float = 90.0, estado: int = ESTADO_VEGETACION_DENSA) -> dict:
    """
    Terreno sintético homogéneo para experimentos de sensibilidad: un solo
    tipo de combustible sobre un plano que sube `pendiente_pct` % hacia
    `azimut_subida` (0 = norte, 90 = este). Devuelve el mismo dict que
    `preparar_terreno`, así que el resto del pipeline no distingue.
    """
    grid = np.full((filas, columnas), estado, dtype=int)
    fila_i, col_i = np.mgrid[0:filas, 0:columnas]
    este_m, norte_m = col_i * tam_celda_m, -fila_i * tam_celda_m
    az = np.radians(azimut_subida)
    elevacion = pendiente_pct / 100.0 * (este_m * np.sin(az) + norte_m * np.cos(az))
    return {
        "filas": filas,
        "columnas": columnas,
        "grid": grid,
        "celda_origen": (filas // 2, columnas // 2),
        "elevacion": elevacion if pendiente_pct else None,
        "datos_geo": None,
        "geografia_real": False,
    }
```

- [ ] **Paso 4: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 41 tests ... OK`

- [ ] **Paso 5: Commit**

```bash
git add entorno_simulacion.py tests/test_terreno.py
git commit -m "$(cat <<'EOF'
feat: terreno controlado (plano con pendiente y combustible únicos) para experimentos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 5 — Laboratorio de sensibilidad

### Tarea 9: `experimentos.py` — un parámetro a la vez, curvas en el tiempo

**Archivos:**
- Crear: `experimentos.py`, `tests/test_experimentos.py`

**Interfaces:**
- Consume: `terreno_controlado` (Tarea 8), `construir_clima_manual`, `SimuladorIncendio` (`llegada`, `lwr_max`; Tarea 5), `CalculadorMetricas(..., origen=...)` (Tarea 4).
- Produce: `correr(clima, pendiente_pct, combustible, pasos=8, lado=201) -> list[dict]` y `barrido(parametro, valores, pasos=8, lado=201) -> list[dict]`, con filas `{parametro, valor, minuto, area_ha, velocidad_m_min, toca_borde, lwr_max}`; `main()` escribe `resultados/barrido.csv` y `resultados/barrido_<parametro>.png`.

- [ ] **Paso 1: Escribir las pruebas que fallan.** Crear `tests/test_experimentos.py`:

```python
import unittest

from experimentos import barrido, correr, CLIMA_BASE
from simulador_automata import ESTADO_VEGETACION_DENSA


def ultimo(filas, valor):
    return [f for f in filas if f["valor"] == valor][-1]


class LaboratorioDeSensibilidad(unittest.TestCase):
    def test_mas_viento_mas_velocidad_y_mas_area(self):
        filas = barrido("viento_velocidad", [0.0, 6.0], pasos=4, lado=81)
        calma, viento = ultimo(filas, 0.0), ultimo(filas, 6.0)
        self.assertGreater(viento["velocidad_m_min"], calma["velocidad_m_min"])
        self.assertGreater(viento["area_ha"], calma["area_ha"])

    def test_mas_humedad_menos_area(self):
        filas = barrido("humedad_relativa", [20.0, 65.0], pasos=4, lado=81)
        self.assertGreater(ultimo(filas, 20.0)["area_ha"], ultimo(filas, 65.0)["area_ha"])

    def test_una_fila_por_paso_y_valor(self):
        filas = barrido("pendiente_pct", [0.0, 30.0], pasos=3, lado=41)
        self.assertEqual(len(filas), 6)
        self.assertEqual([f["minuto"] for f in filas[:3]], [15, 30, 45])

    def test_si_no_puede_arder_el_area_es_cero(self):
        humedo = dict(CLIMA_BASE, temperatura=15.0, humedad_relativa=99.0)
        filas = correr(humedo, 0.0, ESTADO_VEGETACION_DENSA, pasos=2, lado=21)
        self.assertEqual([f["area_ha"] for f in filas], [0.0, 0.0])

    def test_marca_cuando_el_fuego_toca_el_borde(self):
        filas = barrido("viento_velocidad", [6.0], pasos=8, lado=21)
        self.assertTrue(filas[-1]["toca_borde"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Paso 2: Ejecutar y verificar que fallan.**

Run: `python -B -m unittest tests.test_experimentos -v`
Expected: ERROR `ModuleNotFoundError: No module named 'experimentos'`.

- [ ] **Paso 3: Implementar.** Crear `experimentos.py`:

```python
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
```

- [ ] **Paso 4: Ejecutar todas las pruebas.**

Run: `python -B -m unittest discover -s tests -t . -v`
Expected: `Ran 46 tests ... OK` (unos 17 s).

- [ ] **Paso 5: Commit**

```bash
git add experimentos.py tests/test_experimentos.py
git commit -m "$(cat <<'EOF'
feat: laboratorio de sensibilidad (un parámetro a la vez, curvas de velocidad y área)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

### Tarea 10: Correr el barrido y documentar los resultados

**Archivos:**
- Crear: `resultados/barrido.csv`, `resultados/barrido_*.png` (generados)
- Modificar: `README.md`, `CLAUDE.md`

- [ ] **Paso 1: Ejecutar el barrido.**

Run: `python -B experimentos.py`
Expected: seis líneas `<parametro>: listo` (unos 30 s) y los archivos en `resultados/`.

- [ ] **Paso 2: Revisar los resultados.** Abrir cada PNG y el CSV. Verificar que: más viento, más pendiente, menos humedad relativa y combustible vivo más seco dan más velocidad y más área; `toca_borde` es `False` salvo en `combustible = pasto`. Si `toca_borde` es `True` en otro barrido, no interpretar esa curva: subir `LADO` o bajar `PASOS` y repetir.

- [ ] **Paso 3: Documentar.** Agregar a `README.md`, antes de *Limitaciones conocidas*, una sección `## Resultados del laboratorio de sensibilidad` con una tabla por parámetro (valor → área y velocidad de cabeza a los 120 min, leídas del CSV) y estos puntos de discusión, verificando cada uno contra los números reales antes de escribirlo:
  - Efecto relativo de cada parámetro (cuál cambia más el área a las 2 h).
  - La temperatura casi no mueve el fuego: en Rothermel solo actúa vía la humedad del combustible.
  - Con viento suave el área puede no aumentar aunque la cabeza se acelere (la elipse de Anderson se alarga más rápido de lo que Rothermel acelera la cabeza); con viento moderado o fuerte ambos crecen.
  - El pasto con viento sale de la grilla en 2 h: las comparaciones pasto/bosque se leen en los primeros pasos o con una grilla más grande.

- [ ] **Paso 4: `CLAUDE.md`.** En *Comandos reales de este repo*, agregar:

```markdown
- Laboratorio de sensibilidad (escribe `resultados/`): `python -B experimentos.py`
```

- [ ] **Paso 5: Commit**

```bash
git add resultados README.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: resultados del laboratorio de sensibilidad

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

## Fase 6 — Siguientes pasos (fuera de este plan)

Se dejan documentados, sin tareas, hasta que haya una razón concreta para hacerlos:

- **Esquema de Godunov anisotrópico:** elimina la sobreestimación de flancos con LWR > 4 (pasto con viento > ~7 m/s). Solo si el estudio necesita vientos extremos.
- **Validación contra un incendio histórico documentado:** requiere un perímetro real georreferenciado con su clima; es el paso que convertiría la verificación (modelo contra su propia teoría) en validación (modelo contra la realidad).
- **Clasificación de combustible con cobertura global** (ej. ESA WorldCover), en vez de solo las etiquetas de OpenStreetMap.
- **Pavesas (spotting) y fuego de copa.**
- **Mojado del combustible por lluvia.**
- **Heterogeneidad espacialmente correlacionada** del combustible, para estudios de incertidumbre con réplicas.

## Implicaciones para el documento del parcial (no se modifica en este plan)

Cuando se actualice el documento: el *tipo de modelo* pasa de "autómata celular estocástico" a "modelo de frente por conjuntos de nivel sobre una grilla, determinista con heterogeneidad estocástica opcional"; la referencia a Anderson (1969) sobre tiempo de residencia deja de describir el motor; y Finney (1998) pasa a sustentar también la combinación de viento y pendiente.
