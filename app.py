import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import folium
import streamlit.components.v1 as components
import time
import numpy as np

# Se asume que validar_y_sanitizar_clima está en ingesta_clima.py
from ingesta_clima import obtener_coordenadas, obtener_clima_tiempo_real, validar_y_sanitizar_clima
from simulador_automata import SimuladorIncendio
from metricas_fuego import CalculadorMetricas

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

st.title("🔥 Plataforma de Simulación y Análisis de Incendios")

# 3. Panel Lateral Dinámico
with st.sidebar:
    st.markdown("### ⚙️ Configuración del Modelo")
    
    metodo_ubicacion = st.radio("Método de coordenadas:", ["Nombre de Ubicación", "Latitud / Longitud Exacta"])
    
    if metodo_ubicacion == "Nombre de Ubicación":
        lugar_input = st.text_input("Ubicación geográfica:", "Ocaña, Colombia")
        lat_input, lon_input = None, None
    else:
        lugar_input = None
        col_lat, col_lon = st.columns(2)
        lat_input = col_lat.number_input("Latitud:", value=8.243500, format="%.6f")
        lon_input = col_lon.number_input("Longitud:", value=-73.354100, format="%.6f")

    pasos_totales_input = st.number_input("Horizonte (Pasos de 15 min):", min_value=1, max_value=100, value=20)
    velocidad_input = st.slider("Velocidad Visual (s):", 0.1, 1.0, 0.1)
    
    st.markdown("---")
    ejecutar = st.button("🚀 INICIAR SIMULACIÓN", type="primary", use_container_width=True)
    status_bar = st.empty()

# 4. Bloque de ejecución seguro
if ejecutar:
    status_bar.info("📡 Obteniendo y validando datos meteorológicos...")

    try:
        # Resolución de coordenadas
        if metodo_ubicacion == "Nombre de Ubicación":
            lat, lon = obtener_coordenadas(lugar_input)
            if lat is None or lon is None:
                raise ValueError(f"No se pudo localizar '{lugar_input}'. Intenta con coordenadas exactas.")
        else:
            lat, lon = lat_input, lon_input

        # Ingesta y validación
        clima_raw = obtener_clima_tiempo_real(lat, lon)
        clima, alertas_clima = validar_y_sanitizar_clima(clima_raw)

        if alertas_clima:
            st.warning("⚠️ **Datos faltantes:** La API no entregó todas las variables. Usando valores de respaldo:")
            for msj in alertas_clima:
                st.write(msj)

        # Cálculo de riesgo determinista
        riesgo_dinamico = (clima['temperatura'] / 25.0) * (clima['viento_velocidad'] / 3.0) * (clima['vpd'] / 1.5)
        riesgo_dinamico = max(1.0, min(riesgo_dinamico, 30.0))
        np.random.seed(hash(f"{lat}_{lon}_{clima['temperatura']}_{clima['viento_velocidad']}") % (2**32))

        # Panel de Telemetría Superior
        st.markdown("### 📡 Telemetría y Monitoreo en Tiempo Real")
        w1, w2, w3, w4, w5 = st.columns(5)
        w1.metric("Temperatura", f"{clima['temperatura']} °C")
        w2.metric("Humedad Rel.", f"{clima['humedad_relativa']} %")
        w3.metric("Vel. Viento", f"{clima['viento_velocidad']:.1f} m/s")
        w4.metric("Déficit Vap.", f"{clima.get('vpd', 1.2)} kPa")
        w5.metric("Índice Riesgo", f"{riesgo_dinamico:.2f}")
        st.markdown("---")

        # Contenedores visuales dinámicos
        m1, m2, m3, m4, m5 = st.columns(5)
        m1_holder, m2_holder, m3_holder, m4_holder, m5_holder = m1.empty(), m2.empty(), m3.empty(), m4.empty(), m5.empty()

        col_grid, col_map = st.columns(2)
        with col_grid:
            st.markdown("**Matriz Celular Termodinámica**")
            plot_spot = st.empty()
        with col_map:
            st.markdown("**Proyección Satelital (Esri)**")
            map_spot = st.empty()

        sim = SimuladorIncendio(filas=50, columnas=50, tam_celda_m=10)
        metricas = CalculadorMetricas(tam_celda_m=10, minutos_por_paso=15)
        grid_inicial = sim.grid.copy()
        sim.iniciar_incendio(25, 25)

        cmap = ListedColormap(['#0E1117', '#1E8449', '#E74C3C', '#7F8C8D', '#2980B9'])
        lat_deg_per_m = 1.0 / 111000.0
        lon_deg_per_m = 1.0 / (111000.0 * np.cos(np.radians(lat)))

        # Bucle de simulación
        for paso in range(1, pasos_totales_input + 1):
            status_bar.progress(int((paso / pasos_totales_input) * 100), text=f"Paso {paso}/{pasos_totales_input}")

            sim.simular_paso(clima, multiplicador_riesgo=riesgo_dinamico)
            rep = metricas.generar_reporte(grid_inicial, sim.grid, paso)

            m1_holder.metric("Tiempo Simulado", f"{rep['tiempo_minutos']} min")
            m2_holder.metric("Focos Activos", f"{rep['celdas_activas']}")
            m3_holder.metric("Daño Estructural", f"{rep['porcentaje_urbano_afectado']:.1f} %")
            m4_holder.metric("Área Afectada (m²)", f"{rep['area_m2']:,.0f} m²")
            m5_holder.metric("Área Afectada (ha)", f"{rep['area_hectareas']:.2f} ha")

            fig, ax = plt.subplots(figsize=(4.5, 4.5))
            fig.patch.set_facecolor('#0E1117') 
            ax.imshow(sim.grid, cmap=cmap, vmin=0, vmax=4)
            ax.axis('off')
            plot_spot.pyplot(fig)
            plt.close(fig)

            m = folium.Map(
                location=[lat, lon],
                zoom_start=16,
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri",
                zoom_control=False
            )

            fuego_coords = np.argwhere(sim.grid == 2)
            for r, c in fuego_coords:
                c_lat = lat + ((25 - r) * 10 * lat_deg_per_m)
                c_lon = lon + ((c - 25) * 10 * lon_deg_per_m)
                folium.CircleMarker(
                    location=[c_lat, c_lon],
                    radius=3, color="#E74C3C", fill=True, fill_color="#F1C40F", fill_opacity=0.8, weight=0
                ).add_to(m)

            with map_spot:
                components.html(m._repr_html_(), height=380)

            time.sleep(velocidad_input)

        status_bar.success("✅ Simulación finalizada exitosamente.")

    except ValueError as e_val:
        status_bar.empty()
        st.error(f"📍 **Error de ubicación:** {str(e_val)}")
    except KeyError as e_key:
        status_bar.empty()
        st.error(f"🔑 **Falta una variable clave en el modelo:** {str(e_key)}. Revisa tu función 'validar_y_sanitizar_clima'.")
    except Exception as e_gen:
        status_bar.empty()
        st.error(f"❌ **Error inesperado:** {str(e_gen)}")