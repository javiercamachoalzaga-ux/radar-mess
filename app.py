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
        
        # Limpieza exhaustiva de texto para evitar fallos en los filtros
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        
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
            cliente_str = cliente_str.upper()
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
                if "🔴" in sla: return "🚨 RIESGO: Visita presencial. Validar opciones (ej. aclarar que no manejamos acreditación HBW 5/250 para durómetros si aplica)."
                elif "🟡" in sla: return "📞 ALERTA: Llamada para asegurar tiempos de entrega de calibración o venta de equipo."
                else: return "✉️ SEGUIMIENTO: Correo consultivo para mantener presencia."
            else:
                if monto > 15000: return "💼 ALTO VALOR: Agendar visita o videollamada para revisar el alcance técnico a detalle."
                elif "🔴" in sla: return "⏱️ 80/20: Llamada de 5 min. Si hay bloqueo, avanzar al siguiente para no perder tracción."
                else: return "📱 CONTACTO: Mandar un mensaje de seguimiento rápido."

        df['Estrategia_Cierre'] = df.apply(generar_estrategia, axis=1)
        df = df.sort_values(by='Valor_Orden', ascending=False)
        cols_vista = ['SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']

        # ==========================================
        # PREPARACIÓN DE LAS 3 BASES DE DATOS INDEPENDIENTES
        # Aquí solucionamos el error: separamos todo ANTES de las pestañas
        # ==========================================
        df_vip = df[df['Prioridad'] == "⭐ TOP 10"].copy()
        
        df_normal = df[df['Prioridad'] == "Normal"].copy()
        ranking_normal = df_normal.groupby('Cliente')['Valor_Orden'].sum().reset_index().sort_values(by='Valor_Orden', ascending=False)
        top_5_nombres = ranking_normal.head(5)['Cliente'].tolist()
        
        df_potencial = df_normal[df_normal['Cliente'].isin(top_5_nombres)].copy()
        df_general = df_normal[~df_normal['Cliente'].isin(top_5_nombres)].copy()

        # ==========================================
        # PESTAÑAS Y RENDERIZADO
        # ==========================================
        tab_vip, tab_potencial, tab_general = st.tabs(["🏆 VIP", "🚀 Alertas 20-80", "📋 General"])

        # --- PESTAÑA 1: VIP ---
        with tab_vip:
            if not df_vip.empty:
                lista_vip = ["Todos"] + sorted(df_vip['Cliente'].unique().tolist())
                sel_vip = st.selectbox("Filtrar VIP:", lista_vip, key="f_vip")
                
                df_mostrar_vip = df_vip if sel_vip == "Todos" else df_vip[df_vip['Cliente'] == sel_vip]
                
                c1, c2 = st.columns(2)
                c1.metric("Total MXN (Selección)", f"${df_mostrar_vip['Monto_MXN'].sum():,.2f}")
                c2.metric("Total USD (Selección)", f"${df_mostrar_vip['Monto_USD'].sum():,.2f}")
                
                # La llave dinámica evita que el editor se congele
                st.data_editor(df_mostrar_vip[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel_vip}")
            else:
                st.info("Sin cuentas VIP")

        # --- PESTAÑA 2: EMERGENTES ---
        with tab_potencial:
            if not df_potencial.empty:
                lista_pot = ["Todos"] + sorted(df_potencial['Cliente'].unique().tolist())
                sel_pot = st.selectbox("Filtrar Emergentes:", lista_pot, key="f_pot")
                
                df_mostrar_pot = df_potencial if sel_pot == "Todos" else df_potencial[df_potencial['Cliente'] == sel_pot]
                
                c1, c2 = st.columns(2)
                c1.metric("Total MXN (Selección)", f"${df_mostrar_pot['Monto_MXN'].sum():,.2f}")
                c2.metric("Total USD (Selección)", f"${df_mostrar_pot['Monto_USD'].sum():,.2f}")
                
                st.data_editor(df_mostrar_pot[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel_pot}")
            else:
                st.info("Sin cuentas emergentes")

        # --- PESTAÑA 3: CARTERA GENERAL ---
        with tab_general:
            if not df_general.empty:
                lista_gral = ["Todos"] + sorted(df_general['Cliente'].unique().tolist())
                sel_gral = st.selectbox("Filtrar Cartera Base:", lista_gral, key="f_gral")
                
                df_mostrar_gral = df_general if sel_gral == "Todos" else df_general[df_general['Cliente'] == sel_gral]
                
                c1, c2 = st.columns(2)
                c1.metric("Total MXN (Selección)", f"${df_mostrar_gral['Monto_MXN'].sum():,.2f}")
                c2.metric("Total USD (Selección)", f"${df_mostrar_gral['Monto_USD'].sum():,.2f}")
                
                st.data_editor(df_mostrar_gral[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel_gral}")
            else:
                st.info("No hay más clientes en la cartera general.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.write("Por favor sube tu archivo CSV de Scott para empezar.")
