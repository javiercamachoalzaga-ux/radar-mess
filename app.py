import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración
st.set_page_config(page_title="Radar Comercial | MESS", layout="wide")

def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 2. Interfaz y Carga
st.title("🎯 Radar de Cierres 80-20")
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    df = pd.read_csv(archivo_cargado)
    df.columns = df.columns.str.strip()
    
    # TRADUCTOR: Scott -> Nuestro Radar
    traductor = {
        "FOLIO": "Cotización",
        "CLIENTE": "Cliente",
        "AREA": "Parque_Industrial",
        "VALOR": "Monto_MXN",
        "ETAPA": "Temperatura",
        "FECHA DE REGISTRO": "Fecha_Registro"
    }
    df = df.rename(columns=traductor)
    
    # Calculamos días sin contacto basados en FECHA DE REGISTRO
    df['Fecha_Registro'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
    df['Dias_Sin_Contacto'] = (pd.Timestamp.now() - df['Fecha_Registro']).dt.days.fillna(0).astype(int)
    
    # Filtramos solo columnas necesarias
    columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
    df = df[columnas_oro]
    df['Estatus_SLA'] = df['Dias_Sin_Contacto'].apply(lambda x: "🔴 Crítico (>72h)" if x >= 3 else "🟢 Al día")

else:
    # Datos demo si no hay archivo
    df = pd.DataFrame({"Cotización": ["DEMO"], "Cliente": ["Demo"], "Parque_Industrial": ["Qro"], "Monto_MXN": [0], "Dias_Sin_Contacto": [0], "Temperatura": ["Media"], "Estatus_SLA": ["N/A"]})

# 3. Visualización
st.subheader("📊 Visión Financiera")
st.metric("Valor Total Activo", f"${df['Monto_MXN'].sum():,.2f} MXN")

parque_sel = st.selectbox("Parque Industrial:", df['Parque_Industrial'].unique())
df_ruta = df[df['Parque_Industrial'] == parque_sel].copy()
df_ruta['Argumento_de_Cierre'] = ""

df_editado = st.data_editor(df_ruta, hide_index=True)

if st.download_button("📥 Descargar Ruta", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Ruta.csv"):
    st.success("¡Ruta descargada con éxito!")
