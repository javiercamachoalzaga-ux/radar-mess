import streamlit as st
import pandas as pd
import numpy as np

# 1. Configuración
st.set_page_config(page_title="Radar Comercial | MESS", layout="wide")

# 2. Seguridad
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 3. Interfaz
st.title("🎯 Radar de Cierres 80-20")
st.sidebar.header("⚙️ Configuración")
tc = st.sidebar.number_input("Tipo de cambio (USD a MXN)", value=19.50, step=0.10)
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    df = pd.read_csv(archivo_cargado)
    df.columns = df.columns.str.strip()
    
    # Traductor
    traductor = {"FOLIO": "Cotización", "CLIENTE": "Cliente", "AREA": "Parque_Industrial", 
                 "VALOR": "Monto_Bruto", "ETAPA": "Temperatura", "FECHA DE REGISTRO": "Fecha_Registro"}
    df = df.rename(columns=traductor)
    
    # LIMPIEZA ROBUSTA
    def limpiar_y_convertir(fila):
        val_str = str(fila['Monto_Bruto']).upper()
        # Extraer solo números y puntos
        num = float(''.join(c for c in val_str if c.isdigit() or c == '.'))
        # Si contiene 'USD', multiplicamos
        if 'USD' in val_str:
            return num * tc
        return num

    # Aplicamos con manejo de errores interno
    try:
        df['Monto_MXN'] = df.apply(limpiar_y_convertir, axis=1)
    except:
        df['Monto_MXN'] = 0 # Si algo falla, ponemos 0 para no romper la app

    # Días
    df['Fecha_Registro'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
    df['Dias_Sin_Contacto'] = (pd.Timestamp.now() - df['Fecha_Registro']).dt.days.fillna(0).astype(int)
    
    columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
    df = df[columnas_oro]
else:
    df = pd.DataFrame({"Cotización": ["DEMO"], "Monto_MXN": [0], "Parque_Industrial": ["Qro"]})

# 4. Visualización
st.metric("Valor Total Activo (MXN)", f"${df['Monto_MXN'].sum():,.2f} MXN")
df_editado = st.data_editor(df, hide_index=True)

if st.download_button("📥 Descargar Ruta", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Ruta.csv"):
    st.success("¡Ruta descargada!")
