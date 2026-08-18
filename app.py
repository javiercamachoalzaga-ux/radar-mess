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
        # Leemos y limpiamos
        df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
        df.columns = df.columns.str.strip()
        
        traductor = {"COTIZACION": "Cotización", "CLIENTE": "Cliente", "VALOR": "Monto_Bruto", "FECHA": "Fecha_Registro"}
        df = df.rename(columns=lambda x: traductor.get(x, x))
        
        # --- LIMPIEZA DE MONEDAS ---
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
        df['Valor_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # --- ESCÁNER TOP 10 VIP ---
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        def es_vip(cliente_str):
            cliente_str = str(cliente_str).upper()
            for marca in top_10:
                if marca in cliente_str: return "⭐ TOP 10"
            return "Normal"
        df['Prioridad'] = df['Cliente'].apply(es_vip)

        # --- SEMÁFOROS SLA ---
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

        # --- MOTOR DE ESTRATEGIA ---
        def generar_estrategia(fila):
            prioridad = fila['Prioridad']
            sla = fila['SLA']
            monto = fila['Valor_Orden']
            
            if prioridad == "⭐ TOP 10":
                if "🔴" in sla: return "🚨 RIESGO: Visita presencial. Validar si requieren soporte con equipos de medición (aclarar exclusiones)."
                elif "🟡" in sla: return "📞 ALERTA: Llamada gerencial. Asegurar tiempos de entrega de calibración."
                else: return "✉️ SEGUIMIENTO: Correo consultivo. Confirmar recepción."
            else:
                if monto > 15000: return "💼 ALTO VALOR: Agendar visita. Confirmar detalles del alcance acreditado."
                elif "🔴" in sla: return "⏱️ 80/20: Llamada rápida de 5 min. Si hay barreras, descartar temporalmente."
                else: return "📱 CONTACTO: WhatsApp de seguimiento para pulsar temperatura."

        df['Estrategia_Cierre'] = df.apply(generar_estrategia, axis=1)
        
        # Ordenamiento interno por dinero
        df = df.sort_values(by='Valor_Orden', ascending=False)
        cols_vista = ['SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']

        # --- SEPARACIÓN EN PESTAÑAS (TABS) ---
        tab_vip, tab_potencial, tab_general = st.tabs(["🏆 Cuentas VIP", "🚀 Alertas 20-80", "📋 Cartera General"])

        # ==========================================
        # PESTAÑA 1: VIP
        # ==========================================
        with tab_vip:
            df_vip = df[df['Prioridad'] == "⭐ TOP 10"]
            if not df_vip.empty:
                st.markdown("### 🥇 Ranking de Cuentas Clave")
                ranking_vip = df_vip.groupby('Cliente')['Valor_Orden'].sum().reset_index()
                ranking_vip = ranking_vip.sort_values(by='Valor_Orden', ascending=False).reset_index(drop=True)
                ranking_vip.index += 1
                st.dataframe(ranking_vip.rename(columns={'Valor_Orden': 'Valor Total Estimado (MXN)'}).style.format({'Valor Total Estimado (MXN)': '${:,.2f}'}), use_container_width=True)
                
                st.markdown("### 🔍 Filtrar Detalle VIP")
                lista_vip = ["Todos"] + sorted(df_vip['Cliente'].unique().tolist())
                sel_vip = st.selectbox("Selecciona una cuenta VIP:", lista_vip, key="filtro_vip")
                
                df_mostrar_vip = df_vip if sel_vip == "Todos" else df_vip[df_vip['Cliente'] == sel_vip]
                
                col1, col2 = st.columns(2)
                col1.metric("Total MXN (Selección)", f"${df_mostrar_vip['Monto_MXN'].sum():,.2f}")
                col2.metric("Total USD (Selección)", f"${df_mostrar_vip['Monto_USD'].sum():,.2f}")
                
                st.data_editor(df_mostrar_vip[cols_vista], hide_index=True, use_container_width=True, key="vip_edit")
            else:
                st.info("Sin cotizaciones VIP activas en este reporte.")

        # ==========================================
        # PESTAÑA 2: RADAR 20-80
        # ==========================================
        with tab_potencial:
            df_normal = df[df['Prioridad'] == "Normal"]
            if not df_normal.empty:
                st.markdown("### 🚀 Top 5 Cuentas Emergentes")
                st.write("Clientes fuera de tu Top 10 concentrando alto volumen. Posibles candidatos a trato preferencial.")
                
                ranking_normal = df_normal.groupby('Cliente')['Valor_Orden'].sum().reset_index()
                ranking_normal = ranking_normal.sort_values(by='Valor_Orden', ascending=False)
                candidatos = ranking_normal.head(5)
                st.dataframe(candidatos.rename(columns={'Valor_Orden': 'Valor Total Estimado (MXN)'}).style.format({'Valor Total Estimado (MXN)': '${:,.2f}'}), use_container_width=True)
                
                nombres_candidatos = candidatos['Cliente'].tolist()
                df_alertas = df_normal[df_normal['Cliente'].isin(nombres_candidatos)]
                
                st.markdown("### 🔍 Filtrar Detalle Emergente")
                lista_pot = ["Todos"] + sorted(df_alertas['Cliente'].unique().tolist())
                sel_pot = st.selectbox("Selecciona una cuenta emergente:", lista_pot, key="filtro_pot")
                
                df_mostrar_pot = df_alertas if sel_pot == "Todos" else df_alertas[df_alertas['Cliente'] == sel_pot]
                
                col1, col2 = st.columns(2)
                col1.metric("Total MXN (Selección)", f"${df_mostrar_pot['Monto_MXN'].sum():,.2f}")
                col2.metric("Total USD (Selección)", f"${df_mostrar_pot['Monto_USD'].sum():,.2f}")
                
                st.data_editor(df_mostrar_pot[cols_vista], hide_index=True, use_container_width=True, key="pot_edit")

        # ==========================================
        # PESTAÑA 3: CARTERA GENERAL
        # ==========================================
        with tab_general:
            # Excluimos a los emergentes (Top 5) de esta pestaña para evitar duplicados
            df_resto = df_normal[~df_normal['Cliente'].isin(nombres_candidatos)] if not df_normal.empty else df_normal
            
            if not df_resto.empty:
                st.markdown("### 🔍 Buscar en Cartera Base")
                lista_gral = ["Todos"] + sorted(df_resto['Cliente'].unique().tolist())
                sel_gral = st.selectbox("Selecciona un cliente de la base general:", lista_gral, key="filtro_gral")
                
                df_mostrar_gral = df_resto if sel_gral == "Todos" else df_resto[df_resto['Cliente'] == sel_gral]
                    
                col1, col2 = st.columns(2)
                col1.metric("Total MXN (Selección)", f"${df_mostrar_gral['Monto_MXN'].sum():,.2f}")
                col2.metric("Total USD (Selección)", f"${df_mostrar_gral['Monto_USD'].sum():,.2f}")
                
                st.data_editor(df_mostrar_gral[cols_vista], hide_index=True, use_container_width=True, key="gral_edit")
            else:
                st.info("No hay más clientes en la cartera general.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.write("Por favor sube tu archivo CSV de Scott para empezar.")
