import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración de página
st.set_page_config(page_title="Radar MESS 80-20", layout="wide")

# 2. Seguridad
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 3. Interfaz y Carga
st.title("🎯 Radar de Cierres 80-20")
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    try:
        # Leemos el archivo y limpiamos
        df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
        df.columns = df.columns.str.strip()
        
        # Traductor
        traductor = {
            "COTIZACION": "Cotización", 
            "CLIENTE": "Cliente", 
            "VALOR": "Monto_Bruto",
            "FECHA": "Fecha_Registro"
        }
        df = df.rename(columns=lambda x: traductor.get(x, x))
        
        # --- 1. SEPARACIÓN DE MONEDAS ---
        def procesar_mxn(val_str):
            val_str = str(val_str).upper()
            if 'USD' in val_str: return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        def procesar_usd(val_str):
            val_str = str(val_str).upper()
            if 'USD' not in val_str: return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        df['Monto_MXN'] = df['Monto_Bruto'].apply(procesar_mxn)
        df['Monto_USD'] = df['Monto_Bruto'].apply(procesar_usd)

        # --- 2. ESCÁNER TOP 10 VIP ---
        # Aquí están tus palabras clave. Puedes agregar más en el futuro si tu cartera cambia.
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        
        def es_vip(cliente_str):
            cliente_str = str(cliente_str).upper()
            for marca in top_10:
                if marca in cliente_str:
                    return "⭐ TOP 10"
            return "Normal"
            
        df['Prioridad'] = df['Cliente'].apply(es_vip)

        # --- 3. SEMÁFOROS SLA ---
        if 'Fecha_Registro' in df.columns:
            df['Fecha_Registro'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
            dias_diff = (pd.Timestamp.now().normalize() - df['Fecha_Registro']).dt.days
            
            def semaforo(dias):
                if pd.isna(dias): return "⚪ S/F"
                if dias >= 3: return "🔴 +3 días"
                elif dias == 2: return "🟡 2 días"
                else: return "🟢 Reciente"
                
            df['SLA'] = dias_diff.apply(semaforo)
        else:
            df['SLA'] = "⚪ N/A"

        # --- 4. DOBLE REGLA 80-20 (ORDENAMIENTO) ---
        # Primero agrupa a todos los VIP arriba, y dentro de los VIP y los Normales, los ordena por monto.
        df['Es_VIP_Bool'] = df['Prioridad'] == "⭐ TOP 10"
        df['Valor_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)
        df = df.sort_values(by=['Es_VIP_Bool', 'Valor_Orden'], ascending=[False, False])

        # --- 5. COLUMNA TÁCTICA ---
        df['Estrategia_Cierre'] = ""

        # Preparamos la vista final agregando la columna Prioridad
        columnas_finales = ['Prioridad', 'SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        df_final = df[[c for c in columnas_finales if c in df.columns]]

        # --- VISUALIZACIÓN ---
        st.subheader("📊 Visión Financiera")
        col1, col2 = st.columns(2)
        col1.metric("Total Cotizado MXN", f"${df['Monto_MXN'].sum():,.2f}")
        col2.metric("Total Cotizado USD", f"${df['Monto_USD'].sum():,.2f}")
        
        st.markdown("### 📋 Plan de Ataque")
        # El data_editor permite escribir en la tabla
        df_editado = st.data_editor(df_final, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        if st.download_button("📥 Descargar Plan del Día", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Plan_80_20.csv"):
            st.success("¡Plan descargado! Éxito en tus cierres.")
            
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.write("Por favor sube tu archivo CSV de Scott para empezar.")
