# CLAUDE.md

## Stack

Python 3 puro (sin Flutter/Node/PHP). Aplicación web con **Streamlit** que
simula la propagación de incendios forestales sobre geografía y clima reales.

Sin base de datos ni backend propio: toda entrada externa viene de **APIs
públicas gratuitas de solo lectura** (Nominatim, Overpass/OpenStreetMap,
Open-Meteo), sin llaves ni credenciales que gestionar.

## Comandos reales de este repo

- Instalar dependencias: `pip install -r requirements.txt`
- Levantar la app: `streamlit run app.py` (puerto 8501; ver `.claude/launch.json`)
- Demo de consola / smoke test manual: `python main_prueba.py`
- Pruebas (stdlib, sin pytest; `-B` evita reescribir los `.pyc` versionados):
  `python -B -m unittest discover -s tests -t . -v`
- Verificación rápida de sintaxis:
  `python -m py_compile app.py simulador_automata.py main_prueba.py modelo_rothermel.py modelo_probabilidad.py entorno_simulacion.py ingesta_clima.py ingesta_geografica.py metricas_fuego.py`
- **Formateador/linter: ninguno instalado.** No hay black/ruff/flake8/autopep8
  en el entorno ni configuración (`pyproject.toml`, `.flake8`, etc.). No lo
  inventes ni lo corras automáticamente.

## Convenciones observadas en el código

- Identificadores, docstrings y comentarios **en español**.
- Arquitectura de responsabilidad única por módulo (ver tabla en README.md):
  `ingesta_clima.py` (clima/geocodificación), `ingesta_geografica.py`
  (geografía OSM), `entorno_simulacion.py` (combina terreno + clima),
  `modelo_probabilidad.py` (FFWI/humedad, informativo), `modelo_rothermel.py`
  (física de propagación Rothermel/Anderson), `simulador_automata.py`
  (autómata celular), `metricas_fuego.py` (métricas), `app.py` (interfaz
  Streamlit), `main_prueba.py` (demo de consola).
- El clima no sabe nada del terreno, el terreno no sabe nada del clima; el
  autómata es el único módulo que combina ambos. Esto evita el doble conteo
  de factores climáticos que tenía la versión original del proyecto.
- En `app.py`, los imports pesados (numpy, matplotlib, folium, etc.) van
  **dentro** de `if ejecutar:`, nunca al nivel del módulo — evita que
  Streamlit los recargue en cada carga de página.
- Los comentarios documentan el **porqué**, no el qué. Las constantes físicas
  (modelos de combustible, coeficientes de Rothermel) van siempre citadas con
  su fuente académica — ver `modelo_rothermel.py` y la sección "Referencias
  del motor de propagación" en README.md.

## Reglas

- No hay operaciones destructivas de base de datos porque no hay base de
  datos. El equivalente más cercano es sobrescribir física ya verificada: los
  modelos de combustible y las fórmulas de `modelo_rothermel.py` fueron
  contrastados contra fuentes publicadas y código de referencia (ver README).
  **Cualquier cambio a esas constantes o fórmulas requiere confirmación
  explícita** antes de aplicarse.
- No hay `.gitignore` en este repo; `__pycache__/` y los `.pyc` terminan
  versionados en git. No lo arregles a menos que se pida explícitamente.
- Las llamadas de red van solo a Nominatim, Overpass API (con varios espejos
  de respaldo) y Open-Meteo — todas sin autenticación. No agregues llaves de
  API, proxies, ni cambies esos endpoints sin que te lo pidan.
