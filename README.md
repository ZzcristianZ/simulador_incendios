# Simulador de Incendios Forestales

Simulación de la propagación de un incendio forestal mediante un
**autómata celular estocástico**, parametrizado con **datos ambientales
reales** (clima, terreno y edificaciones) de una ubicación geográfica
dada — por ejemplo, tu propia casa.

> **Nota de terminología:** esto **no** es una simulación en "tiempo
> real" del fuego. El *clima de entrada* sí es tiempo real (se consulta
> en el momento). La *física del fuego* avanza en pasos de tiempo
> discreto: cada paso de simulación representa **15 minutos simulados**
> del incendio, independientemente de cuántos milisegundos tarde en
> dibujarse en pantalla. El término técnico correcto es **simulación de
> un sistema dinámico discreto (autómata celular estocástico)**.

## ¿Qué responde este proyecto?

Dada una dirección o coordenada, y asumiendo que un incendio inicia
**ahora mismo, justo ahí**: ¿qué tan rápido avanza el fuego con el
clima actual, qué edificios reales alrededor se ven afectados y en qué
momento (si acaso) llega a esa ubicación exacta?

## Arquitectura

```
ingesta_clima.py         Clima real (Open-Meteo) y geocodificación (Nominatim)
ingesta_geografica.py    Edificios, agua, bosque y vías reales (OpenStreetMap/Overpass)
entorno_simulacion.py    Junta geografía + elevación + clima en la grilla de simulación
modelo_probabilidad.py   Física de ignición por dirección (clima) + índice Fosberg (FFWI)
simulador_automata.py    Autómata celular vectorizado (numpy): combustible, pendiente, fuego
metricas_fuego.py        Área, velocidad de avance, daño a EDIFICIOS individuales, ETA a "tu casa"
app.py                   Interfaz Streamlit
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
Se pide una malla gruesa de elevación (11×11 puntos) a la API de
elevación de Open-Meteo en una sola consulta, y se interpola
bilinealmente a la resolución fina de la grilla. El fuego se propaga
más rápido cuesta arriba y más lento cuesta abajo, con un factor
exponencial simplificado en la línea de Alexandridis et al. (2008).

### 3. Clima evolutivo (`ingesta_clima.py::obtener_pronostico_horario`)
En vez de una sola fotografía del clima "actual" repetida durante toda
la corrida, se trae el pronóstico horario real y cada paso de 15
minutos usa el clima de su hora correspondiente.

### 4. Probabilidad de ignición (`modelo_probabilidad.py`)
Para cada una de las 8 direcciones vecinas, la probabilidad de que el
fuego salte combina multiplicativamente: temperatura, humedad
relativa, déficit de presión de vapor (VPD), humedad del suelo,
radiación solar, precipitación (corte total si llueve) y viento
(velocidad, ráfagas y ángulo respecto a la dirección del viento).

### 5. Autómata celular (`simulador_automata.py`)
Vectorizado con numpy: como el clima es uniforme sobre toda el área en
un instante dado, la probabilidad climática de una dirección se calcula
**una sola vez por paso** (no una vez por celda), y se combina con
arrays de pendiente y de tipo de combustible. Esto lo hace lo bastante
rápido para simular grillas más grandes y finas que la versión
original. El pasto arde y se consume rápido; el bosque arde más
intenso y por más tiempo; lo urbano es más resistente a encenderse
pero, una vez en llamas, tarda más en consumirse (incendio
estructural).

### 6. Métricas y daño a estructuras (`metricas_fuego.py`)
El daño urbano ya no se mide solo en "% de celdas quemadas": las
celdas urbanas contiguas se agrupan como **edificios individuales**
(componentes conexas), así que el reporte dice, por ejemplo,
"3 de 12 edificios afectados". También se estima cuántos minutos
faltan para que el fuego llegue a tu casa (si aún no ha llegado),
usando la distancia al frente activo más cercano y la velocidad media
de avance observada.

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

- El modelo es un autómata celular de 8 vecinos, no un modelo físico
  completo de combustión (no reemplaza herramientas profesionales como
  FARSITE o FlamMap).
- Overpass API es un servicio público con límites de uso; en horas
  pico puede responder lento o fallar (de ahí el respaldo sintético).
- La malla de elevación es gruesa (11×11) e interpolada; no captura
  variaciones de terreno muy locales.
- El factor de escenario es una herramienta deliberada de análisis de
  sensibilidad, no una corrección automática — el valor por defecto
  (1.0) usa el clima medido tal cual.

## Posibles extensiones futuras

- Propagación de pavesas (spotting): ignición a distancia por ráfagas.
- Validación contra el perímetro real de un incendio histórico conocido.
- Exportar el reporte final a PDF para el informe de la materia.
- Tiempo de evacuación estimado por vía (usando las vías ya extraídas
  de OpenStreetMap como red, no solo como cortafuego).
