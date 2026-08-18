import streamlit as st
import pandas as pd

# 1. Configuración
st.set_page_config(page_title="Radar MESS", layout="wide")

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
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    # Leemos y quitamos filas vacías que veo en tu tabla
    df = pd.read_csv(archivo_cargado).dropna(subset=['COTIZACION', 'CLIENTE'])
    df.columns = df.columns.str.strip()
    
    # Traductor actualizado a tus columnas reales
    traductor = {
        "COTIZACION": "Cotización", 
        "CLIENTE": "Cliente", 
        "VALOR": "Monto_Bruto"
    }
    df = df.rename(columns=traductor)
    
    # LIMPIEZA: Solo números para el monto
    def limpiar_monto(x):
        try:
            # Quitamos todo lo que no sea dígito o punto
            return float(''.join(c for c in str(x) if c.isdigit() or c == '.'))
        except: return 0.0

    df['Monto_MXN'] = df['Monto_Bruto'].apply(limpiar_monto)
    
    # Mostramos los datos limpios
    st.subheader("📊 Visión Financiera")
    st.metric("Total Cotizado", f"${df['Monto_MXN'].sum():,.2f} MXN")
    
    st.data_editor(df[['Cotización', 'Cliente', 'Monto_MXN']], hide_index=True)
    
    if st.download_button("📥 Descargar", data=df.to_csv(index=False).encode('utf-8-sig'), file_name="Ruta_Limpia.csv"):
        st.success("Descargado")
else:
    st.write("Por favor sube tu archivo CSV de Scott para empezar.")
