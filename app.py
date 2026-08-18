import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title="Radar Comercial | MESS", layout="wide")

# 2. Funciones auxiliares
def calcular_semaforo(dias):
    try:
        dias = int(dias)
        if dias >= 3: return "🔴 Crítico (>72h)"
        elif dias == 2: return "🟡 Atención (48h)"
        else: return "🟢 Al día"
    except: return "⚪ N/A"

def cargar_datos_demo():
    data = {
        "Cotización": ["MESS-001"], "Cliente": ["Demo"], "Parque_Industrial": ["Qro"],
        "Monto_MXN": [1000], "Dias_Sin_Contacto": [1], "Temperatura": ["Media"]
    }
    return pd.DataFrame(data)

# 3. Seguridad
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]:
        return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 4. Interfaz y Carga
st.title("🎯 Radar de Cierres 80-20")
archivo_cargado = st.sidebar.file_uploader("Subir CSV", type=["csv"])

if archivo_cargado is not None:
    try:
        df = pd.read_csv(archivo_cargado)
        # Limpieza: quitamos espacios en blanco de los nombres de columnas
        df.columns = df.columns.str.strip()
        
        columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
        df = df[columnas_oro]
        df['Estatus_SLA'] = df['Dias_Sin_Contacto'].apply(calcular_semaforo)
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.write("Columnas detectadas:", df.columns.tolist())
        st.stop()
else:
    df = cargar_datos_demo()

# 5. Visualización
st.subheader("📊 Visión Financiera")
st.metric("Valor Total Activo", f"${df['Monto_MXN'].sum():,.2f} MXN")

st.markdown("---")
parque_sel = st.selectbox("Parque Industrial:", df['Parque_Industrial'].unique())
df_ruta = df[df['Parque_Industrial'] == parque_sel].copy()
df_ruta['Argumento_de_Cierre'] = ""

df_editado = st.data_editor(df_ruta, hide_index=True)

if st.download_button("📥 Descargar Ruta", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Ruta.csv"):
    st.success("Descargado")
