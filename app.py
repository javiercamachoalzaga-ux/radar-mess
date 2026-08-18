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

# Menú lateral para tipo de cambio
st.sidebar.header("⚙️ Configuración")
tc = st.sidebar.number_input("Tipo de cambio (USD a MXN)", value=19.50, step=0.10)
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    df = pd.read_csv(archivo_cargado)
    df.columns = df.columns.str.strip()
    
    traductor = {"FOLIO": "Cotización", "CLIENTE": "Cliente", "AREA": "Parque_Industrial", 
                 "VALOR": "Monto_Bruto", "ETAPA": "Temperatura", "FECHA DE REGISTRO": "Fecha_Registro"}
    df = df.rename(columns=traductor)
    
    # LÓGICA DE MONEDA
    def convertir_a_mxn(valor_str, tipo_cambio):
        valor_str = str(valor_str).upper()
        # Limpiamos caracteres
        num = float(''.join(c for c in valor_str if c.isdigit() or c == '.'))
        # Si dice USD, multiplicamos por el tipo de cambio
        if 'USD' in valor_str:
            return num * tipo_cambio
        return num # Si no, asumimos MXN

    df['Monto_MXN'] = df['Monto_Bruto'].apply(lambda x: convertir_a_mxn(x, tc))
    
    # Días sin contacto
    df['Fecha_Registro'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
    df['Dias_Sin_Contacto'] = (pd.Timestamp.now() - df['Fecha_Registro']).dt.days.fillna(0).astype(int)
    
    columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
    df = df[columnas_oro]
else:
    df = pd.DataFrame({"Cotización": ["DEMO"], "Cliente": ["Demo"], "Parque_Industrial": ["Qro"], 
                       "Monto_MXN": [0], "Dias_Sin_Contacto": [0], "Temperatura": ["Media"]})

# 3. Visualización
st.subheader("📊 Visión Financiera (Totalizado en MXN)")
st.metric("Valor Total Activo", f"${df['Monto_MXN'].sum():,.2f} MXN")

parque_sel = st.selectbox("Parque Industrial:", df['Parque_Industrial'].unique())
df_ruta = df[df['Parque_Industrial'] == parque_sel].copy()
df_ruta['Argumento_de_Cierre'] = ""

df_editado = st.data_editor(df_ruta, hide_index=True)

if st.download_button("📥 Descargar Ruta", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Ruta.csv"):
    st.success("¡Ruta descargada!")
