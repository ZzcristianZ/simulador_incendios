# Simulador de Incendios Forestales

Simulación de la propagación de un incendio forestal mediante un
**frente de fuego sobre una grilla (método de conjuntos de nivel)**, parametrizado con **datos ambientales
reales** (clima, terreno y edificaciones) de una ubicación geográfica
dada — por ejemplo, tu propia casa.

> **Nota de terminología:** esto **no** es una simulación en "tiempo
> real" del fuego. El *clima de entrada* sí es tiempo real (se consulta
> en el momento). La *física del fuego* avanza en pasos de tiempo
> discreto: cada paso de simulación representa **15 minutos simulados**
> del incendio, independientemente de cuántos milisegundos tarde en
> dibujarse en pantalla. El término técnico correcto es **simulación de
> un sistema dinámico discreto (frente por conjuntos de nivel sobre una grilla)**.

## ¿Qué responde este proyecto?

Dada una dirección o coordenada, y asumiendo que un incendio inicia
**ahora mismo, justo ahí** (esa coordenada es únicamente el punto de
origen del incendio, no un lugar que haya que "proteger"): ¿qué tan
rápido avanza el fuego con el clima actual, qué tan grande es el área
afectada (en m² y hectáreas) y qué edificios reales alrededor se ven
afectados?

## Arquitectura

```
ingesta_clima.py         Clima real (Open-Meteo) y geocodificación (Nominatim)
ingesta_geografica.py    Edificios, agua, bosque y vías reales (OpenStreetMap/Overpass, con espejos)
entorno_simulacion.py    Junta geografía + elevación + clima (real o manual) en la grilla de simulación
modelo_probabilidad.py   Índice Fosberg (FFWI) e insumo de humedad de combustible, informativos
modelo_rothermel.py      Física de propagación real: Rothermel (1972) + elipse de viento (Anderson 1983)
simulador_automata.py    Frente de fuego por conjuntos de nivel (numpy): combustible, pendiente, viento
metricas_fuego.py        Área (m² y ha), velocidad de avance, daño a EDIFICIOS individuales
app.py                   Interfaz Streamlit (modo tiempo real y modo condiciones controladas)
main_prueba.py           Demo por consola, sin interfaz gráfica
```

Cada módulo tiene una sola responsabilidad: el clima no sabe nada del
terreno, el terreno no sabe nada del clima, y el autómata es el único
que combina ambos. Esto evita un error que tenía la versión original
del proyecto, donde un "índice de riesgo" volvía a calcular
temperatura/viento/VPD y multiplicaba una probabilidad que **ya**
incluía esos mismos factores (doble conteo). Ahora ese control está
explícito como un **factor de escenario** que por defecto es 1.0
(condiciones tal cual medidas) y que puedes subir deliberadamente para
un análisis de sensibilidad.

## El modelo, paso a paso

### 1. Terreno real (`ingesta_geografica.py`)
Se consulta Overpass API (OpenStreetMap) por edificios, cuerpos de
agua, bosque/arbolado y vías en un radio configurable alrededor del
punto. Cada polígono real se **rasteriza** (se convierte a celdas) en
la grilla del autómata. Si Overpass no responde, se usa un terreno
sintético de respaldo para que la simulación no se detenga.

Estados de celda: `vegetación ligera` (pasto/matorral, por defecto),
`vegetación densa` (bosque real), `urbano` (edificio real), `agua`,
`sin combustible` (vías) y, durante la simulación, `fuego` / `quemado`.

### 2. Elevación y pendiente (`ingesta_clima.py::obtener_elevacion_grid`)
Se pide una malla gruesa de elevación (10×10 = 100 puntos, el máximo
que acepta la API de elevación de Open-Meteo por consulta) en una sola
llamada, y se interpola bilinealmente a la resolución fina de la
grilla. La pendiente real (por dirección) alimenta el coeficiente de
pendiente de Rothermel (ver punto 5): el fuego se propaga más rápido
cuesta arriba y más lento cuesta abajo.

### 3. Clima evolutivo o condiciones controladas (`ingesta_clima.py`, `entorno_simulacion.py`)
Dos modos, elegibles en la barra lateral:
- **Tiempo real (API):** se trae el pronóstico horario real de
  Open-Meteo y cada paso de 15 minutos usa el clima de su hora
  correspondiente (o el clima "actual" fijo, si se desactiva el
  pronóstico evolutivo).
- **Condiciones controladas (manual):** el usuario fija a mano las
  mismas variables que devuelve la API (temperatura, humedad relativa,
  viento en velocidad/ráfagas/dirección, precipitación, radiación
  solar, humedad de suelo, VPD), y ese único escenario se mantiene
  constante durante toda la corrida. Útil para un análisis de
  sensibilidad puro ("¿qué pasaría si el viento fuera de 40 km/h desde
  el norte, sin importar qué clima haga hoy realmente ahí?"). El
  terreno (edificios/agua/bosque/elevación) sigue siendo real en ambos
  modos; solo cambia la fuente del clima.

### 4. Velocidad real de propagación (`modelo_rothermel.py`)
El núcleo del motor ya no es una fórmula ad-hoc: es el **modelo de
propagación superficial de Rothermel (1972)** — el mismo motor
matemático detrás de BehavePlus y FARSITE — combinado con la **elipse
de forma de incendio impulsada por viento de Anderson (1983)**. Para
cada dirección de la vecindad de Moore, se calcula una velocidad de
avance real en **metros/minuto**, no una probabilidad inventada.

- **Modelos de combustible estándar:** la vegetación ligera (pasto,
  por defecto) usa el modelo FBFM1 "Short grass" y la vegetación densa
  (bosque real de OSM) usa el FBFM10 "Timber, litter and understory",
  ambos de la tabla estándar de Anderson, H.E. (1982), *Aids to
  Determining Fuel Models for Estimating Fire Behavior*, USDA
  GTR-INT-122 (carga por clase de tamaño, razón superficie/volumen,
  profundidad de cama de combustible, humedad de extinción).
- **Ecuaciones núcleo:** intensidad de reacción con amortiguación por
  humedad y minerales, packing ratio, flujo de propagación,
  coeficientes de viento y pendiente — Rothermel, R.C. (1972), *A
  Mathematical Model for Predicting Fire Spread in Wildland Fuels*,
  USDA GTR-INT-115, con el refinamiento del coeficiente de viento de
  Albini, F.A. (1976) GTR-INT-30. La implementación se portó y verificó
  contra el código fuente del paquete R `Rothermel` (Vacchiano & Ascoli
  2015, *Fire Technology* 51(3)) y se validó numéricamente contra las
  velocidades de referencia publicadas para ambos modelos de
  combustible.
- **Viento y pendiente combinados como vectores (Finney 1998):** el
  coeficiente de viento de Rothermel apunta hacia donde sopla el viento y
  el de pendiente cuesta arriba; su resultante da la velocidad de cabeza y
  su dirección. La forma del incendio (razón largo/ancho de Anderson, 1983)
  sale del *viento efectivo*, el viento que por sí solo produciría ese
  mismo efecto. Cuesta abajo el fuego retrocede más lento que en llano.
- **Humedad de combustible:** la humedad de los combustibles muertos se
  deriva del contenido de humedad de equilibrio (EMC) a partir de
  temperatura y humedad relativa — la misma fórmula que ya usaba el
  índice Fosberg, ahora compartida en vez de duplicada. La humedad de
  los combustibles vivos (solo aplica al bosque) no tiene fuente
  climática en tiempo real, así que usa una constante estacional
  documentada en el código.
- **Lo urbano no es Rothermel:** ese modelo es solo para combustible
  silvestre. Una estructura se aproxima como una fracción (heurística)
  de la velocidad que tendría la vegetación ligera en ese punto, bajo
  el mismo viento y pendiente — representa exposición a radiación y
  pavesas de celdas vecinas en llamas, no combustión de materiales de
  construcción.

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

**¿Y si el clima no da para que arda ni el punto de origen?** Antes de
encender el fuego, `SimuladorIncendio.puede_arder` verifica que
Rothermel realmente calcule una velocidad mayor que 0 ahí — es decir,
que la humedad del combustible (derivada de temperatura/humedad
relativa vía EMC) no supere su humedad de extinción (12% pasto, 25%
bosque). Si la supera, no se fuerza la ignición: el modelo dice, con
razón, que no hay combustión física posible (como intentar prender un
fósforo en pasto empapado), y la app lo explica en vez de reportar un
"incendio" fantasma de una sola celda. El **factor de escenario** no
puede saltarse este umbral: multiplica la velocidad ya calculada, y
cualquier número multiplicado por 0 sigue siendo 0.

### 6. Métricas y daño a estructuras (`metricas_fuego.py`)
El daño urbano ya no se mide solo en "% de celdas quemadas": las
celdas urbanas contiguas se agrupan como **edificios individuales**
(componentes conexas), así que el reporte dice, por ejemplo,
"3 de 12 edificios afectados". El área afectada se reporta tanto en m²
como en hectáreas.

### 7. Índice Fosberg (FFWI)
Se muestra, solo con fines informativos (no alimenta el motor de
probabilidad), el Fosberg Fire Weather Index — un índice real y
citable (Fosberg, M.A., 1978) que resume qué tan propicias son las
condiciones climáticas actuales para el fuego.

## Cómo correrlo

```bash
pip install -r requirements.txt
streamlit run app.py
```

O la demo de consola (sin interfaz gráfica):

```bash
python main_prueba.py
```

Ambos requieren conexión a internet: Nominatim (geocodificación),
Overpass API (edificios/agua/bosque), y Open-Meteo (clima y
elevación) — todos servicios públicos y gratuitos, sin llave de API.

## Limitaciones conocidas (para tu informe)

- El frente usa un esquema de conjuntos de nivel de primer orden: con
  elipses muy alargadas (LWR > 4, pasto con viento fuerte) sobreestima el
  área de los flancos (+35% con LWR 8). La app lo avisa; la mejora es un
  esquema de Godunov anisotrópico.
- La temperatura solo actúa a través de la humedad del combustible (EMC),
  así que su efecto directo es pequeño; no se modela el precalentamiento.
- La lluvia pausa el avance pero no moja el combustible.
- Solo hay 2 modelos de combustible silvestre (pasto y bosque), porque
  la clasificación de vegetación de este proyecto viene únicamente de
  OpenStreetMap (sin una fuente global de cobertura de suelo): fuera de
  zonas etiquetadas como bosque real, todo se trata como pasto.
- La humedad de los combustibles vivos (solo relevante para el bosque)
  no tiene fuente climática en tiempo real; usa una constante estacional
  documentada en `modelo_rothermel.py`, no un dato medido.
- Lo urbano no tiene un modelo de combustión propio: es una heurística
  de exposición estructural, documentada como tal.
- Overpass API es un servicio público con límites de uso; en horas pico
  puede responder lento o fallar (de ahí los espejos alternativos y,
  como último recurso, el respaldo sintético).
- La malla de elevación es gruesa (10×10, el máximo de la API de
  Open-Meteo por consulta) e interpolada; no captura variaciones de
  terreno muy locales.
- El factor de escenario es una herramienta deliberada de análisis de
  sensibilidad, no una corrección automática — el valor por defecto
  (1.0) usa el clima medido (o manual) tal cual.

## Referencias del motor de propagación

- Rothermel, R.C. (1972). *A Mathematical Model for Predicting Fire
  Spread in Wildland Fuels*. USDA Forest Service, GTR-INT-115.
- Albini, F.A. (1976). *Estimating Wildfire Behavior and Effects*. USDA
  Forest Service, GTR-INT-30.
- Anderson, H.E. (1982). *Aids to Determining Fuel Models for
  Estimating Fire Behavior*. USDA Forest Service, GTR-INT-122.
- Anderson, H.E. (1983). *Predicting Wind-Driven Wild Land Fire Size
  and Shape*. USDA Forest Service, RP-INT-305.
- Anderson, H.E. (1969). *Heat Transfer and Fire Spread*. USDA Forest
  Service, RP-INT-69 (tiempo de residencia de llama).
- Vacchiano, G. & Ascoli, D. (2015). "An Implementation of the
  Rothermel Fire Spread Model in the R Programming Language". *Fire
  Technology*, 51(3) — la implementación de este proyecto se portó y
  verificó contra el código fuente de ese paquete.
- Fosberg, M.A. (1978). *Weather in Wildland Fire Management: The Fire
  Weather Index* (índice Fosberg, informativo).
- Alexandridis, A. et al. (2008). "A cellular automata model for forest
  fire spread prediction" (enfoque general de autómata celular).
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

## Posibles extensiones futuras

- Propagación de pavesas (spotting): ignición a distancia por ráfagas.
- Clasificación de vegetación con una fuente global de cobertura de
  suelo (ej. ESA WorldCover), en vez de depender solo de las etiquetas
  de OpenStreetMap.
- Esquema de Godunov anisotrópico para elipses muy alargadas (LWR > 4).
- Validación contra el perímetro real de un incendio histórico conocido.
- Exportar el reporte final a PDF para el informe de la materia.
- Tiempo de evacuación estimado por vía (usando las vías ya extraídas
  de OpenStreetMap como red, no solo como cortafuego).
