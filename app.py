import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title="Radar Comercial | MESS", layout="wide", initial_sidebar_state="expanded")

# 2. Sistema de Seguridad (Contraseña)
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if pwd == st.secrets["mi_contrasena"]:
        return True
    elif pwd != "":
        st.sidebar.error("Contraseña incorrecta")
    return False

if not check_password():
    st.info("Por favor, ingresa tu contraseña en el menú lateral para acceder al sistema.")
    st.stop()

# 3. Funciones auxiliares
def calcular_semaforo(dias):
    if dias >= 3: return "🔴 Crítico (>72h)"
    elif dias == 2: return "🟡 Atención (48h)"
    else: return "🟢 Al día"

def cargar_datos_demo():
    data = {
        "Cotización": ["MESS-CT-001", "MESS-CT-002", "MESS-CT-003"],
        "Cliente": ["Empresa Demo 1", "Empresa Demo 2", "Empresa Demo 3"],
        "Parque_Industrial": ["Bernardo Quintana", "El Marqués", "Benito Juárez"],
        "Monto_MXN": [150000, 45000, 85000],
        "Dias_Sin_Contacto": [4, 1, 2],
        "Temperatura": ["Alta", "Baja", "Media"]
    }
    df = pd.DataFrame(data)
    df['Estatus_SLA'] = df['Dias_Sin_Contacto'].apply(calcular_semaforo)
    return df

# 4. Interfaz principal
st.title("🎯 Radar de Cierres 80-20")
st.markdown("Plataforma de gestión comercial y priorización de rutas.")

with st.sidebar:
    st.markdown("---")
    st.header("⚙️ Motor de Datos")
    st.info("Arrastra aquí tu exportación del sistema Scott.")
    archivo_cargado = st.file_uploader("Subir CSV de Cotizaciones", type=["csv"])

# 5. Procesamiento de datos
if archivo_cargado is not None:
    df = pd.read_csv(archivo_cargado)
    
    # Asumimos que tu CSV tiene exactamente estas 6 columnas:
    columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
    
    try:
        df = df[columnas_oro]
        df['Estatus_SLA'] = df['Dias_Sin_Contacto'].apply(calcular_semaforo)
    except KeyError:
        st.error("⚠️ Error: Las columnas del CSV no coinciden. Revisa que se llamen exactamente igual que la plantilla.")
        st.stop()
else:
    df = cargar_datos_demo()

# 6. Tablero de KPIs
st.subheader("📊 Visión Financiera")
col1, col2, col3 = st.columns(3)
col1.metric("Valor Total Activo", f"${df['Monto_MXN'].sum():,.2f} MXN")
col2.metric("Capital en Riesgo", f"${df[df['Dias_Sin_Contacto'] >= 3]['Monto_MXN'].sum():,.2f} MXN")
col3.metric("Oportunidades Altas", len(df[df['Temperatura'] == 'Alta']))

# 7. Generador de Rutas y Estrategia
st.markdown("---")
st.subheader("📍 Planeación de Ruta y Táctica")

parques = df['Parque_Industrial'].unique().tolist()
parque_seleccionado = st.selectbox("Selecciona el Parque Industrial a atacar:", parques)
df_ruta = df[df['Parque_Industrial'] == parque_seleccionado].sort_values(by="Monto_MXN", ascending=False)

df_ruta['Argumento_de_Cierre'] = ""
st.info("💡 Haz doble clic en la última columna para anotar tu argumento técnico (ej. 'No hay alcance Brinell HBW 5/250' o 'Son 315 muestras') antes de descargar.")

df_ruta_editada = st.data_editor(
    df_ruta[['Estatus_SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Temperatura', 'Argumento_de_Cierre']],
    use_container_width=True, hide_index=True,
    disabled=['Estatus_SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Temperatura']
)

# 8. Descarga de Archivo
st.markdown("<br>", unsafe_allow_html=True)
csv_ruta = df_ruta_editada.to_csv(index=False).encode('utf-8-sig')

colA, colB = st.columns([1, 3])
with colA:
    fecha_hoy = datetime.today().strftime('%Y-%m-%d')
    st.download_button(
        label="📥 Descargar Ruta con Notas",
        data=csv_ruta,
        file_name=f"Ruta_{parque_seleccionado}_{fecha_hoy}.csv",
        mime="text/csv",
        use_container_width=True
    )
