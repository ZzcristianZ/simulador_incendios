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

# 2. CSS optimizado para alta densidad
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 2rem; padding-right: 2rem; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    div[data-testid="metric-container"] { margin-bottom: -15px; }
    h1 { font-size: 1.8rem !important; margin-bottom: 0rem !important; padding-bottom: 0rem !important;}
    h3 { font-size: 1.2rem !important; margin-top: 0rem !important; margin-bottom: 0.5rem !important;}
    </style>
""", unsafe_allow_html=True)

st.title("🔥 Plataforma de Simulación y Análisis de Incendios Forestales")
st.caption(
    "Autómata celular estocástico alimentado con clima, edificios, agua y "
    "vegetación reales del lugar que ingreses. No es una simulación en "
    "tiempo real: cada paso representa 15 minutos de avance del fuego."
)

# 3. Panel Lateral Dinámico
with st.sidebar:
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
        }
    else:
        usar_clima_evolutivo = st.checkbox("Clima evolutivo por hora (pronóstico real)", value=True,
                                            help="Si se desactiva, se usa el clima actual fijo durante toda la simulación.")

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
            ["Tiempo Simulado", "Focos Activos", "Edificios Afectados", "Área Afectada", "Vel. Propagación"],
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
        sim.iniciar_incendio(fila_origen, col_origen)

        metricas = CalculadorMetricas(tam_celda_m=TAM_CELDA_M, minutos_por_paso=MINUTOS_POR_PASO)

        # Paleta: 0 quemado, 1 veg. ligera, 2 fuego, 3 urbano, 4 agua, 5 sin combustible, 6 veg. densa
        cmap = ListedColormap(['#0E1117', '#1E8449', '#E74C3C', '#7F8C8D', '#2980B9', '#B9770E', '#145A32'])
        lat_deg_per_m = 1.0 / 111320.0
        lon_deg_per_m = 1.0 / (111320.0 * np.cos(np.radians(lat)))
        centro_fila, centro_col = filas // 2, columnas // 2

        def _render_grid():
            fig, ax = plt.subplots(figsize=(4.5, 4.5))
            fig.patch.set_facecolor('#0E1117')
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

        # Vista inicial (origen ya encendido) mientras se resuelve el clima.
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

        # --- 4. Bucle de simulación ---
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
            m5_holder.metric("Vel. Propagación", f"{rep['velocidad_m_min']:.1f} m/min")

            _render_grid()
            _render_mapa()

            time.sleep(velocidad_input)

        status_bar.success("✅ Simulación finalizada exitosamente.")

        rep_final = metricas.generar_reporte(grid_inicial_reportes, sim.grid, pasos_totales_input)
        st.markdown(
            f"**Resumen final:** {rep_final['edificios_afectados']} de {rep_final['edificios_totales']} "
            f"edificios detectados en el área fueron afectados · {rep_final['area_m2']:,.0f} m² "
            f"({rep_final['area_hectareas']:.2f} ha) quemadas o en llamas · velocidad media de avance "
            f"{rep_final['velocidad_m_min']:.1f} m/min."
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
