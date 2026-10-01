import streamlit as st

# Nota: los imports pesados (numpy, matplotlib, folium, scipy vía
# entorno_simulacion/metricas_fuego) se hacen DENTRO del bloque `if
# ejecutar:`, no aquí arriba. Si estuvieran a este nivel, Streamlit los
# cargaría en cada carga de la página (incluida la primera vez que
# alguien entra al sitio, antes de que exista un click en el botón),
# lo que se siente como que la app "ya está haciendo algo" mientras en
# realidad solo está importando librerías. Con el import diferido, la
# pantalla inicial aparece de inmediato en su estado normal y el
# trabajo pesado arranca únicamente al pulsar "INICIAR SIMULACIÓN".

# 1. Configuración panorámica
st.set_page_config(page_title="Simulador de Incendios", layout="wide", initial_sidebar_state="expanded")

# 2. Consola neumórfica (soft UI). Colores base, fuentes y radios viven en
# .streamlit/config.toml; aquí solo lo que el tema de Streamlit no puede
# expresar: el par de sombras clara/oscura. Dos tratamientos, nunca uno solo:
#   - relieve (extruido): lo que el sistema entrega o lo que se acciona
#     -> paneles del sidebar, tiles de telemetría, marcos de pantalla, botón.
#   - ranura (hundido): donde el usuario escribe o donde el sistema avisa
#     -> text/number inputs, barra de progreso, avisos.
# Acentos: ember (#FF6B35) solo en el botón de inicio = fuego/acción; teal
# (#5FD4D0) en lecturas y controles = instrumentación. Contraste verificado
# (WCAG): texto #E8E6E3 12.99:1 sobre fondo / 11.71:1 sobre superficie;
# atenuado #8B93A1 5.23:1 / 4.71:1; teal 8.20:1 sobre superficie (donde se
# usa: tiles de telemetría; 9.11:1 sería sobre el fondo base, no donde el
# texto aparece); texto del botón #1A0F0A 6.63:1 sobre ember. Fuera a
# propósito: fondo casi negro, un solo acento,
# terracota, etiquetas en mayúsculas con tracking y una misma sombra gris
# plana para todo (el kit genérico de "tarjetas SaaS").
# Se inyecta en cada rerun con el mismo contenido y en la misma posición,
# así que Streamlit no lo duplica ni lo repinta.
st.markdown("""
    <style>
    :root {
        --panel-bg: #1C2128;
        --panel-surface: #232935;
        --shadow-dark: #12151B;
        --shadow-light: #2E3644;
        --ember: #FF6B35;
        --ember-glow: #FF8F5C;
        --telemetry: #5FD4D0;
        --text-primary: #E8E6E3;
        --text-muted: #8B93A1;
        --relieve: 6px 6px 14px var(--shadow-dark), -5px -5px 12px var(--shadow-light);
        --relieve-corto: 4px 4px 9px var(--shadow-dark), -3px -3px 8px var(--shadow-light);
        --ranura: inset 3px 3px 6px var(--shadow-dark), inset -2px -2px 5px var(--shadow-light);
        --anillo: 2px solid var(--ember-glow);
        --fuente-dato: "Space Grotesk", "Inter", sans-serif;
    }

    .block-container { padding-top: 1rem; padding-bottom: 1.5rem; padding-left: 2rem; padding-right: 2rem; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    h1 { font-size: 1.8rem !important; margin-bottom: 0rem !important; padding-bottom: 0rem !important;}
    h3 { font-size: 1.2rem !important; margin-top: 0rem !important; margin-bottom: 0.5rem !important;}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--text-muted); }

    /* El sidebar es la misma superficie que el área principal; lo separa un
       borde en relieve, no otro color. */
    [data-testid="stSidebar"] { box-shadow: 5px 0 14px var(--shadow-dark); }
    [data-testid="stSidebar"] h3 { font-size: 1.05rem !important; }

    /* Paneles del sidebar (st.container con key="panel_*"): extruidos. */
    [class*="st-key-panel_"] {
        background: var(--panel-surface);
        border-radius: 20px;
        padding: 1rem 1rem 1.15rem;
        box-shadow: var(--relieve);
        margin-bottom: 0.6rem;
    }

    /* Entradas: ranuras hundidas en el panel. El borde nativo de Streamlit
       (showWidgetBorder/borderColor en config.toml) se conserva: en reposo
       da un borde sutil de 1px que convive con la sombra, y de regalo trae
       el borde nativo de foco/error (number_input) que antes quedaba
       anulado. El foco además lo remarca el anillo de abajo. */
    [data-testid="stTextInputRootElement"],
    [data-testid="stNumberInputContainer"] {
        background: var(--panel-bg);
        border-radius: 10px;
        box-shadow: var(--ranura);
    }
    [data-testid="stTextInputRootElement"] input,
    [data-testid="stNumberInputContainer"] input,
    [data-testid="stNumberInputContainer"] button {
        background: transparent;
        color: var(--text-primary);
    }
    [data-testid="stNumberInputContainer"] button:hover { background: transparent; color: var(--telemetry); }
    /* Casilla y radio sin marcar: pequeña ranura con borde atenuado; sin él
       quedan en ~1.2:1 contra el panel (WCAG 1.4.11 pide 3:1; así queda 4.7:1). */
    [data-testid="stCheckbox"] label:not([data-selected="true"]) > span + div {
        background: var(--panel-bg);
        border-color: var(--text-muted);
        box-shadow: inset 2px 2px 4px var(--shadow-dark);
    }
    [data-testid="stRadioOption"]:not([data-selected="true"]) > span + div > div > div:first-child {
        background: var(--panel-bg);
        box-shadow: inset 0 0 0 1px var(--text-muted), inset 2px 2px 4px var(--shadow-dark);
    }
    /* Casilla y radio marcados: el check/punto blanco por defecto queda en
       1.78:1 contra el teal de fondo del control. Se repinta con --panel-bg
       (oscuro) para subir el contraste a ~9.11:1. */
    [data-testid="stCheckbox"] label[data-selected="true"] svg { stroke: var(--panel-bg); }
    [data-testid="stRadioOption"][data-selected="true"] > span + div > div > div:first-child > div { background: var(--panel-bg); }

    /* Foco visible en todo control: anillo ember separado del borde. */
    .stApp :focus-visible { outline: var(--anillo) !important; outline-offset: 2px; }
    [data-testid="stTextInputRootElement"]:focus-within,
    [data-testid="stNumberInputContainer"]:focus-within { outline: var(--anillo); outline-offset: 2px; }
    [data-testid="stCheckbox"] label[data-focus-visible="true"],
    [data-testid="stRadioOption"][data-focus-visible="true"] { outline: var(--anillo); outline-offset: 3px; border-radius: 6px; }
    [data-testid="stSlider"] [data-focus-visible="true"] { outline: var(--anillo); outline-offset: 3px; }

    /* El botón de inicio: el único elemento audaz de la página. Extruido y
       con brillo ember; al presionarlo la sombra se invierte y se hunde. */
    .stApp [data-testid="stBaseButton-primary"] {
        background: linear-gradient(145deg, var(--ember-glow) 0%, var(--ember) 55%);
        color: #1A0F0A;
        border: none;
        border-radius: 16px;
        min-height: 3.25rem;
        box-shadow: 7px 7px 16px var(--shadow-dark), -5px -5px 13px var(--shadow-light),
                    0 0 22px rgba(255, 107, 53, 0.28);
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }
    .stApp [data-testid="stBaseButton-primary"] p {
        font-family: var(--fuente-dato);
        font-weight: 700;
        font-size: 1.02rem;
        color: inherit;
    }
    .stApp [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(145deg, #FFA277 0%, var(--ember-glow) 55%);
        color: #1A0F0A;
        border: none;
        box-shadow: 7px 7px 16px var(--shadow-dark), -5px -5px 13px var(--shadow-light),
                    0 0 30px rgba(255, 143, 92, 0.42);
    }
    /* Deshabilitado (p.ej. pérdida de conexión): debe distinguirse del botón
       activo. Va después de :hover para ganar por orden de aparición a
       especificidad igual. */
    .stApp [data-testid="stBaseButton-primary"]:disabled {
        background: var(--panel-surface);
        color: var(--text-muted);
        box-shadow: var(--ranura);
        cursor: not-allowed;
    }
    .stApp [data-testid="stBaseButton-primary"]:active {
        background: var(--ember);
        color: #1A0F0A;
        transform: translateY(1px);
        box-shadow: inset 5px 5px 12px rgba(122, 38, 8, 0.6), inset -4px -4px 10px rgba(255, 190, 150, 0.35);
    }
    .stApp [data-testid="stBaseButton-primary"]:focus-visible { outline-offset: 4px; }

    /* Telemetría: tiles extruidos; número en Space Grotesk teal, etiqueta
       pequeña y atenuada en Inter. */
    [data-testid="stMetric"] {
        background: var(--panel-surface);
        border-radius: 14px;
        padding: 0.65rem 0.75rem 0.7rem;
        box-shadow: var(--relieve-corto);
    }
    /* Seis tiles por fila no caben en ventanas medianas: mejor que la lectura
       pase a dos líneas a que Streamlit la corte con "…". */
    [data-testid="stMetricLabel"] p, [data-testid="stMetricValue"] p { white-space: normal; }
    /* ...y que los tiles de una misma fila igualen su altura cuando eso pasa. */
    [data-testid="stColumn"]:has([data-testid="stMetric"]) > [data-testid="stVerticalBlock"],
    [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]),
    [data-testid="stMetric"] { height: 100%; }
    [data-testid="stMetricLabel"] p { font-size: 0.8rem; color: var(--text-muted); }
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] p {
        font-family: var(--fuente-dato);
        color: var(--telemetry);
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
    }
    /* Delta del área afectada: se deja el color nativo de Streamlit para el
       delta (sin override) -- un gris propio aquí quedaba en 3.61:1 contra
       el fondo del tile, bajo el mínimo AA de 4.5:1. */

    /* Pantallas (grilla y mapa): marco extruido con la imagen dentro. */
    [data-testid="stElementContainer"]:has(> [data-testid="stFullScreenFrame"] [data-testid="stImage"]),
    [data-testid="stElementContainer"]:has(> iframe[data-testid="stIFrame"]) {
        background: var(--panel-surface);
        border-radius: 18px;
        padding: 0.6rem;
        box-shadow: var(--relieve);
    }
    [data-testid="stImage"] img { border-radius: 12px; }
    /* El iframe del mapa mide 380px fijos, pero el mapa de folium adentro es
       responsivo (alto = 60% del ancho, más 8px de margen del body arriba y
       abajo): sin este ajuste el marco mostraría una franja vacía debajo.
       ponytail: acoplado al ratio por defecto de folium (60%); si se le pasa
       otro ratio a folium.Map/Figure, actualizar este 60cqw. */
    [data-testid="stElementContainer"]:has(> iframe[data-testid="stIFrame"]) {
        container-type: inline-size;
        padding: 2px;
    }
    iframe[data-testid="stIFrame"] { height: calc(60cqw + 6.4px) !important; }

    /* Avisos: conservan su color semántico, levemente hundidos. */
    [data-testid="stAlertContainer"] {
        border-radius: 12px;
        box-shadow: inset 2px 2px 5px rgba(18, 21, 27, 0.75), inset -2px -2px 5px rgba(46, 54, 68, 0.55);
    }
    [data-testid="stProgressBarTrack"] { background: var(--panel-bg); box-shadow: var(--ranura); }

    /* Separador: una hendidura (línea oscura + línea de luz), no una raya plana. */
    hr { border: 0 !important; border-top: 1px solid var(--shadow-dark) !important;
         border-bottom: 1px solid var(--shadow-light) !important; background: none; }
    </style>
""", unsafe_allow_html=True)

st.title("🔥 Plataforma de Simulación y Análisis de Incendios Forestales")
st.caption(
    "Frente de fuego de Rothermel sobre una grilla (conjuntos de nivel), con "
    "clima, edificios, agua y vegetación reales del lugar que ingreses. Cada "
    "paso representa 15 minutos de avance del fuego."
)

# 3. Panel Lateral Dinámico
with st.sidebar:
    with st.container(key="panel_ubicacion"):
        st.markdown("### 📍 Ubicación")
        lugar_input = st.text_input(
            "Dirección o lugar (punto de origen del incendio):", "Ocaña, Colombia",
            help="Mientras más exacta la dirección, más preciso el punto donde 'inicia' el incendio."
        )
        usar_coords_manuales = st.checkbox("Usar latitud/longitud exactas en vez de una dirección")
        if usar_coords_manuales:
            col_lat, col_lon = st.columns(2)
            lat_input = col_lat.number_input("Latitud:", value=8.243500, format="%.6f")
            lon_input = col_lon.number_input("Longitud:", value=-73.354100, format="%.6f")
        else:
            lat_input, lon_input = None, None

    with st.container(key="panel_clima"):
        st.markdown("### 🌦️ Clima")
        modo_clima = st.radio(
            "Fuente del clima:", ["🌐 Tiempo real (API)", "🎛️ Condiciones controladas (manual)"],
            help="En tiempo real se consulta el clima actual/pronóstico de Open-Meteo. En condiciones "
                 "controladas fijas tú mismo cada variable y se mantiene constante durante toda la corrida "
                 "(útil para un escenario hipotético o un análisis de sensibilidad)."
        )
        clima_manual_valores = None
        if modo_clima.startswith("🎛️"):
            usar_clima_evolutivo = False
            cm1, cm2 = st.columns(2)
            clima_manual_valores = {
                "temperatura": cm1.number_input("Temperatura (°C):", value=25.0, step=1.0),
                "humedad_relativa": cm2.number_input("Humedad relativa (%):", value=50.0, min_value=0.0, max_value=100.0, step=1.0),
                "viento_velocidad": cm1.number_input("Viento, velocidad (m/s):", value=3.0, min_value=0.0, step=0.5),
                "viento_rafagas": cm2.number_input("Viento, ráfagas (m/s):", value=4.0, min_value=0.0, step=0.5),
                "viento_direccion": cm1.number_input("Viento, dirección (0-360°):", value=0.0, min_value=0.0, max_value=360.0, step=10.0),
                "precipitacion": cm2.number_input("Precipitación (mm):", value=0.0, min_value=0.0, step=1.0),
                "radiacion_solar": cm1.number_input("Radiación solar (W/m²):", value=200.0, min_value=0.0, step=50.0),
                "humedad_suelo": cm2.number_input("Humedad de suelo (m³/m³):", value=0.30, min_value=0.0, max_value=1.0, step=0.05),
                "vpd": cm1.number_input("Déficit de presión de vapor (kPa):", value=1.2, min_value=0.0, step=0.1),
                "humedad_combustible_vivo": cm2.number_input(
                    "Humedad combustible vivo (%):", value=100.0, min_value=30.0, max_value=250.0, step=10.0,
                    help="Solo afecta al bosque. 100% es un valor estacional típico; más bajo = vegetación más seca."),
            }
        else:
            usar_clima_evolutivo = st.checkbox("Clima evolutivo por hora (pronóstico real)", value=True,
                                                help="Si se desactiva, se usa el clima actual fijo durante toda la simulación.")

    with st.container(key="panel_modelo"):
        st.markdown("### ⚙️ Configuración del Modelo")
        radio_input = st.slider("Radio del área simulada (m):", 150, 600, 300, step=50,
                                 help="Área cuadrada alrededor del punto elegido. Radios grandes cubren más terreno pero con menos detalle por edificio.")
        pasos_totales_input = st.number_input("Horizonte (Pasos de 15 min):", min_value=1, max_value=100, value=20)
        velocidad_input = st.slider("Velocidad Visual (s):", 0.1, 1.0, 0.1)

        incluir_pendiente = st.checkbox("Efecto de pendiente del terreno (elevación real)", value=True)
        multiplicador_escenario = st.slider(
            "Factor de escenario (sensibilidad):", 0.5, 5.0, 1.0, step=0.5,
            help="1.0 = condiciones medidas, sin amplificar. Súbelo para explorar un escenario más severo del que hay ahora mismo (útil para un análisis de sensibilidad en tu informe)."
        )

    st.markdown("---")
    ejecutar = st.button("🚀 INICIAR SIMULACIÓN", type="primary", use_container_width=True)
    status_bar = st.empty()

TAM_CELDA_M = 10
MINUTOS_POR_PASO = 15

# 4. Bloque de ejecución seguro
if ejecutar:
    status_bar.info("📍 Resolviendo ubicación...")

    try:
        import time
        import numpy as np
        import matplotlib.pyplot as plt
        from matplotlib.colors import ListedColormap
        import folium
        import streamlit.components.v1 as components

        from ingesta_clima import obtener_coordenadas
        from simulador_automata import SimuladorIncendio, ESTADO_FUEGO
        from metricas_fuego import CalculadorMetricas
        from modelo_probabilidad import calcular_ffwi
        from entorno_simulacion import (
            preparar_terreno, preparar_serie_climatica, construir_clima_manual, clima_en_paso,
        )

        # --- Layout completo primero, ANTES de cualquier llamada de red:
        # así el usuario ve de inmediato dónde va a aparecer cada dato, en
        # vez de quedarse mirando solo la barra de progreso mientras se
        # resuelve la ubicación / se consulta OSM / se trae el clima. Cada
        # placeholder se rellena apenas ese dato concreto está listo.
        st.markdown("### 📡 Telemetría y Condiciones de Partida")
        w1, w2, w3, w4, w5, w6 = st.columns(6)
        w1_holder, w2_holder, w3_holder = w1.empty(), w2.empty(), w3.empty()
        w4_holder, w5_holder, w6_holder = w4.empty(), w5.empty(), w6.empty()
        for holder, etiqueta in zip(
            [w1_holder, w2_holder, w3_holder, w4_holder, w5_holder, w6_holder],
            ["Temperatura", "Humedad Rel.", "Vel. Viento", "Déficit Vap.", "Índice Fosberg", "Geografía"],
        ):
            holder.metric(etiqueta, "…")
        caption_holder = st.empty()
        st.markdown("---")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1_holder, m2_holder, m3_holder = m1.empty(), m2.empty(), m3.empty()
        m4_holder, m5_holder = m4.empty(), m5.empty()
        for holder, etiqueta in zip(
            [m1_holder, m2_holder, m3_holder, m4_holder, m5_holder],
            ["Tiempo Simulado", "Focos Activos", "Edificios Afectados", "Área Afectada", "Vel. de cabeza"],
        ):
            holder.metric(etiqueta, "…")

        col_grid, col_map = st.columns(2)
        with col_grid:
            st.markdown("**Matriz Celular Termodinámica**")
            plot_spot = st.empty()
            plot_spot.info("⏳ Esperando geografía del terreno...")
        with col_map:
            st.markdown("**Proyección Satelital (Esri)**")
            map_spot = st.empty()
            map_spot.info("⏳ Esperando geografía del terreno...")

        # --- 1. Ubicación ---
        if usar_coords_manuales:
            lat, lon = lat_input, lon_input
        else:
            lat, lon = obtener_coordenadas(lugar_input)
            if lat is None or lon is None:
                raise ValueError(f"No se pudo localizar '{lugar_input}'. Intenta con coordenadas exactas.")

        # --- 2. Terreno real: en cuanto llega, ya se puede dibujar la
        # grilla y el mapa (con el punto de origen), sin esperar el clima.
        status_bar.info("🗺️ Obteniendo edificios, agua y vegetación reales (OpenStreetMap)...")
        entorno = preparar_terreno(lat, lon, radio_input, TAM_CELDA_M, incluir_pendiente)
        filas, columnas = entorno["filas"], entorno["columnas"]

        w6_holder.metric("Geografía", "Real (OSM)" if entorno["geografia_real"] else "Sintética")
        if not entorno["geografia_real"]:
            st.warning("⚠️ No se pudo consultar OpenStreetMap en este momento. Se usó un terreno sintético de respaldo (una franja de agua y un bloque urbano genéricos) para que la simulación pueda continuar.")
        if incluir_pendiente and entorno["elevacion"] is None:
            st.info("ℹ️ No se pudo obtener el modelo de elevación; la simulación continúa sin efecto de pendiente.")

        sim = SimuladorIncendio(
            filas=filas, columnas=columnas, tam_celda_m=TAM_CELDA_M,
            grid_inicial=entorno["grid"], elevacion=entorno["elevacion"],
        )
        fila_origen, col_origen = entorno["celda_origen"]
        grid_inicial_reportes = sim.grid.copy()
        # OJO: todavía NO se enciende el fuego aquí -- primero hace falta
        # el clima de partida para saber si la combustión es siquiera
        # sostenible en ese punto (ver más abajo, `sim.puede_arder`).

        metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=MINUTOS_POR_PASO,
                                      origen=(fila_origen, col_origen))

        # Paleta: 0 quemado, 1 veg. ligera, 2 fuego, 3 urbano, 4 agua, 5 sin combustible, 6 veg. densa
        cmap = ListedColormap(['#0E1117', '#1E8449', '#E74C3C', '#7F8C8D', '#2980B9', '#B9770E', '#145A32'])
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * np.cos(np.radians(lat)))
        centro_fila, centro_col = filas // 2, columnas // 2

        def _render_grid():
            fig, ax = plt.subplots(figsize=(4.5, 4.5))
            fig.patch.set_facecolor('#1C2128')  # --panel-bg: mismo sistema visual que el resto del panel, no un negro aparte.
            ax.imshow(sim.grid, cmap=cmap, vmin=0, vmax=6)
            ax.axis('off')
            plot_spot.pyplot(fig)
            plt.close(fig)

        def _render_mapa():
            m = folium.Map(
                location=[lat, lon],
                zoom_start=17,
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                zoom_control=False
            )

            datos_geo = entorno.get("datos_geo")
            if datos_geo:
                for poligono in datos_geo.get("edificios", []):
                    folium.Polygon(locations=poligono, color="#7F8C8D", weight=1,
                                   fill=True, fill_opacity=0.4).add_to(m)
                for poligono in datos_geo.get("agua", []):
                    folium.Polygon(locations=poligono, color="#2980B9", weight=1,
                                   fill=True, fill_opacity=0.4).add_to(m)
                for poligono in datos_geo.get("bosque", []):
                    folium.Polygon(locations=poligono, color="#145A32", weight=1,
                                   fill=True, fill_opacity=0.25).add_to(m)

            folium.Marker(
                location=[lat, lon], tooltip="🔥 Origen del incendio",
                icon=folium.Icon(color="red", icon="fire", prefix="fa"),
            ).add_to(m)

            fuego_coords = np.argwhere(sim.grid == ESTADO_FUEGO)
            for r, c in fuego_coords:
                c_lat = lat + ((centro_fila - r) * TAM_CELDA_M * lat_deg_per_m)
                c_lon = lon + ((c - centro_col) * TAM_CELDA_M * lon_deg_per_m)
                folium.CircleMarker(
                    location=[c_lat, c_lon],
                    radius=3, color="#E74C3C", fill=True, fill_color="#F1C40F", fill_opacity=0.8, weight=0
                ).add_to(m)

            with map_spot:
                components.html(m._repr_html_(), height=380)

        # Vista inicial del terreno (sin fuego todavía) mientras se
        # resuelve el clima.
        _render_grid()
        _render_mapa()

        # --- 3. Clima: real (API) o condiciones controladas (manual) ---
        if clima_manual_valores is not None:
            status_bar.info("🎛️ Aplicando condiciones climáticas controladas...")
            serie_clima, alertas_clima, clima_evolutivo = construir_clima_manual(clima_manual_valores)
        else:
            status_bar.info("🌦️ Obteniendo clima real (Open-Meteo)...")
            serie_clima, alertas_clima, clima_evolutivo = preparar_serie_climatica(
                lat, lon, pasos_totales_input, MINUTOS_POR_PASO, permitir_evolutivo=usar_clima_evolutivo
            )

        if alertas_clima:
            st.warning("⚠️ **Datos climáticos faltantes:** La API no entregó todas las variables. Usando valores de respaldo:")
            for msj in alertas_clima:
                st.write(msj)

        clima_inicial = clima_en_paso(serie_clima, 1, MINUTOS_POR_PASO)
        ffwi = calcular_ffwi(clima_inicial)

        w1_holder.metric("Temperatura", f"{clima_inicial['temperatura']} °C")
        w2_holder.metric("Humedad Rel.", f"{clima_inicial['humedad_relativa']} %")
        w3_holder.metric("Vel. Viento", f"{clima_inicial['viento_velocidad']:.1f} m/s")
        w4_holder.metric("Déficit Vap.", f"{clima_inicial.get('vpd', 1.2):.2f} kPa")
        w5_holder.metric("Índice Fosberg", f"{ffwi['valor']} ({ffwi['categoria']})")
        if clima_manual_valores is not None:
            texto_clima = "condiciones controladas (manual, constante durante toda la corrida)"
        elif clima_evolutivo:
            texto_clima = "evolutivo (pronóstico horario real)"
        else:
            texto_clima = "fijo durante toda la corrida (clima actual)"
        caption_holder.caption(
            f"Clima {texto_clima} · "
            f"Pendiente {'activada' if entorno['elevacion'] is not None else 'desactivada'}."
        )

        # --- 4. ¿Se puede siquiera encender el fuego con este clima? ---
        # Rothermel calcula velocidad = 0 cuando la humedad del combustible
        # supera su humedad de extinción (12% pasto / 25% bosque): ahí no
        # hay combustión posible, así que forzar la ignición igual solo
        # produciría un "quemado" fantasma de 1 celda (100 m² con la
        # resolución por defecto) sin que el modelo respalde que eso
        # realmente pasaría.
        if not sim.puede_arder(fila_origen, col_origen, clima_inicial):
            rep_sin_fuego = metricas.generar_reporte(grid_inicial_reportes, sim.grid, 0)
            m1_holder.metric("Tiempo Simulado", "0 min")
            m2_holder.metric("Focos Activos", "0")
            m3_holder.metric("Edificios Afectados", f"0 / {rep_sin_fuego['edificios_totales']}")
            m4_holder.metric("Área Afectada", "0 m²", delta="0.00 ha", delta_color="off")
            m5_holder.metric("Vel. de cabeza", "0.0 m/min")
            _render_grid()
            _render_mapa()
            status_bar.warning("🧯 No se pudo sostener combustión")
            st.warning(
                "🧯 **Con el clima de partida, el combustible en el punto de origen está "
                "demasiado húmedo para sostener un incendio.** Rothermel calcula una "
                "humedad de extinción del 12% para pasto y 25% para bosque; con la "
                "temperatura/humedad relativa dadas, la humedad de equilibrio del "
                "combustible ya la supera, así que la velocidad de propagación es 0 "
                "incluso justo en el punto de ignición (como pasarle un fósforo a pasto "
                "empapado: no prende, no se apaga solo). Subir el **factor de escenario** "
                "no cambia esto: es un umbral físico del modelo, no una escala continua. "
                "Probá con clima más seco/cálido, o fijalo vos mismo en modo "
                "**condiciones controladas**."
            )
        else:
            sim.iniciar_incendio(fila_origen, col_origen)

            # --- 5. Bucle de simulación ---
            for paso in range(1, pasos_totales_input + 1):
                status_bar.progress(int((paso / pasos_totales_input) * 100), text=f"Paso {paso}/{pasos_totales_input}")

                clima_paso = clima_en_paso(serie_clima, paso, MINUTOS_POR_PASO)
                sim.simular_paso(clima_paso, multiplicador_riesgo=multiplicador_escenario)
                rep = metricas.generar_reporte(grid_inicial_reportes, sim.grid, paso)

                m1_holder.metric("Tiempo Simulado", f"{rep['tiempo_minutos']} min")
                m2_holder.metric("Focos Activos", f"{rep['celdas_activas']}")
                m3_holder.metric("Edificios Afectados", f"{rep['edificios_afectados']} / {rep['edificios_totales']}")
                m4_holder.metric(
                    "Área Afectada", f"{rep['area_m2']:,.0f} m²",
                    delta=f"{rep['area_hectareas']:.2f} ha", delta_color="off",
                )
                m5_holder.metric("Vel. de cabeza", f"{rep['velocidad_m_min']:.1f} m/min")

                _render_grid()
                _render_mapa()

                time.sleep(velocidad_input)

            status_bar.success("✅ Simulación finalizada exitosamente.")

            rep_final = metricas.generar_reporte(grid_inicial_reportes, sim.grid, pasos_totales_input)
            st.markdown(
                f"**Resumen final:** {rep_final['edificios_afectados']} de {rep_final['edificios_totales']} "
                f"edificios detectados en el área fueron afectados · {rep_final['area_m2']:,.0f} m² "
                f"({rep_final['area_hectareas']:.2f} ha) quemadas o en llamas · velocidad de cabeza "
                f"{rep_final['velocidad_m_min']:.1f} m/min."
            )

            if sim.lwr_max > 4.0:
                st.info(
                    f"ℹ️ Con este viento la elipse del incendio es muy alargada (LWR {sim.lwr_max:.1f} > 4): "
                    "el área de los flancos puede estar sobreestimada. Rango validado del modelo: LWR ≤ 4."
                )
            if np.isfinite(sim.llegada[[0, -1], :]).any() or np.isfinite(sim.llegada[:, [0, -1]]).any():
                st.warning(
                    "⚠️ El incendio alcanzó el borde del área simulada: desde ahí el área real sería mayor. "
                    "Aumenta el radio para verlo completo. La velocidad de cabeza mostrada corresponde al "
                    "último tramo medible antes de tocar el borde."
                )

    except ValueError as e_val:
        status_bar.empty()
        st.error(f"📍 **Error de ubicación:** {str(e_val)}")
    except KeyError as e_key:
        status_bar.empty()
        st.error(f"🔑 **Falta una variable clave en el modelo:** {str(e_key)}. Revisa 'validar_y_sanitizar_clima'.")
    except Exception as e_gen:
        status_bar.empty()
        st.error(f"❌ **Error inesperado:** {str(e_gen)}")
