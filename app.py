import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración de página
st.set_page_config(page_title="Radar Comercial 80-20", layout="wide")

# --- DISEÑO MODERNO ---
st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
    }
    .titulo-radar {
        font-size: 42px;
        font-weight: 900;
        background: -webkit-linear-gradient(45deg, #1e3c72, #2a5298, #00C6FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: -10px;
    }
    .subtitulo {
        font-size: 16px;
        color: #6c757d;
        margin-bottom: 25px;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Seguridad
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 3. Encabezado principal
st.markdown('<div class="titulo-radar">⚡ Radar Comercial 80/20</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia Táctica, Bateo y Proyectos 2026</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott (Histórico Completo)", type=["csv"])

if archivo_cargado is not None:
    try:
        # Leemos y limpiamos
        df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
        df.columns = df.columns.str.strip()
        
        # --- NUEVO: TRADUCTOR CON PROYECTOS ---
        traductor = {
            "COTIZACION": "Cotización", 
            "CLIENTE": "Cliente", 
            "VALOR": "Monto_Bruto",
            "VALOR ": "Monto_Bruto", # Cubre si viene con espacio
            "FECHA": "Fecha_Registro", 
            "ESTATUS": "Estatus",
            "PROYECTO": "ID_Proyecto",
            "DESCRIPCION": "Descripcion_Proyecto",
            "CONTACTO": "Nombre_Contacto"
        }
        df = df.rename(columns=lambda x: traductor.get(x, x))
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        
        if 'Estatus' not in df.columns:
            df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
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
        
        # Variable interna de ordenamiento
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # --- ESCÁNER TOP 10 VIP ---
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        def es_vip(cliente_str):
            cliente_str = cliente_str.upper()
            for marca in top_10:
                if marca in cliente_str: return "⭐ TOP 10"
            return "Normal"
        df['Prioridad'] = df['Cliente'].apply(es_vip)

        # --- CÁLCULO SEPARADO DE HIT RATE ---
        mxn_ganado = df[df['Estatus'].str.contains('GANAD', na=False)]['Monto_MXN'].sum()
        mxn_perdido = df[df['Estatus'].str.contains('PERDID|CANCELAD', na=False)]['Monto_MXN'].sum()
        mxn_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)]['Monto_MXN'].sum()
        
        usd_ganado = df[df['Estatus'].str.contains('GANAD', na=False)]['Monto_USD'].sum()
        usd_perdido = df[df['Estatus'].str.contains('PERDID|CANCELAD', na=False)]['Monto_USD'].sum()
        usd_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)]['Monto_USD'].sum()
        
        total_cerrado_mxn = mxn_ganado + mxn_perdido
        total_cerrado_usd = usd_ganado + usd_perdido
        
        hit_rate_mxn = (mxn_ganado / total_cerrado_mxn * 100) if total_cerrado_mxn > 0 else 0
        hit_rate_usd = (usd_ganado / total_cerrado_usd * 100) if total_cerrado_usd > 0 else 0

        # --- PANEL LATERAL ---
        st.sidebar.markdown("---")
        st.sidebar.header("📈 Hit Rate Real")
        st.sidebar.metric("Bateo Histórico MXN", f"{hit_rate_mxn:.1f}%")
        st.sidebar.metric("Bateo Histórico USD", f"{hit_rate_usd:.1f}%")
        
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Simulador Futuro")
        tasa_mxn = st.sidebar.slider("Simulador Bateo MXN (%)", min_value=0, max_value=100, value=int(hit_rate_mxn) if hit_rate_mxn > 0 else 30, step=5)
        tasa_usd = st.sidebar.slider("Simulador Bateo USD (%)", min_value=0, max_value=100, value=int(hit_rate_usd) if hit_rate_usd > 0 else 30, step=5)

        # --- PREPARACIÓN DE ACTIVAS PARA TÁCTICA ---
        df_activas = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        
        if 'Fecha_Registro' in df_activas.columns:
            df_activas['Fecha_Registro'] = pd.to_datetime(df_activas['Fecha_Registro'], errors='coerce')
            dias_diff = (pd.Timestamp.now().normalize() - df_activas['Fecha_Registro']).dt.days
            def semaforo(dias):
                if pd.isna(dias): return "⚪ S/F"
                if dias >= 3: return "🔴 +3 días"
                elif dias == 2: return "🟡 2 días"
                else: return "🟢 Reciente"
            df_activas['SLA'] = dias_diff.apply(semaforo)
        else:
            df_activas['SLA'] = "⚪ N/A"

        def generar_estrategia(fila):
            prioridad = fila['Prioridad']
            sla = fila['SLA']
            monto = fila['Peso_Interno_Orden']
            
            if prioridad == "⭐ TOP 10":
                if "🔴" in sla: return "🚨 RIESGO: Visita presencial técnica."
                elif "🟡" in sla: return "📞 ALERTA: Llamada consultiva."
                else: return "✉️ SEGUIMIENTO: Correo de presencia."
            else:
                if monto > 15000: return "💼 ALTO VALOR: Visita/Llamada de revisión técnica."
                elif "🔴" in sla: return "⏱️ 80/20: Descartar si hay bloqueo en llamada."
                else: return "📱 CONTACTO: Mensaje de seguimiento."

        df_activas['Estrategia_Cierre'] = df_activas.apply(generar_estrategia, axis=1)
        df_activas = df_activas.sort_values(by='Peso_Interno_Orden', ascending=False)
        
        # Verificamos si están las nuevas columnas para la vista
        cols_base = ['SLA', 'Cotización']
        if 'ID_Proyecto' in df_activas.columns: cols_base.append('ID_Proyecto')
        cols_base.extend(['Cliente'])
        if 'Nombre_Contacto' in df_activas.columns: cols_base.append('Nombre_Contacto')
        cols_base.extend(['Monto_MXN', 'Monto_USD', 'Estrategia_Cierre'])
        
        cols_vista = [c for c in cols_base if c in df_activas.columns]

        # --- SEPARACIÓN TÁCTICA ---
        df_vip = df_activas[df_activas['Prioridad'] == "⭐ TOP 10"].copy()
        df_normal = df_activas[df_activas['Prioridad'] == "Normal"].copy()
        
        ranking_normal = df_normal.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index().sort_values(by='Peso_Interno_Orden', ascending=False)
        top_5_nombres = ranking_normal.head(5)['Cliente'].tolist()
        
        df_potencial = df_normal[df_normal['Cliente'].isin(top_5_nombres)].copy()
        df_general = df_normal[~df_normal['Cliente'].isin(top_5_nombres)].copy()

        # ==========================================
        # PESTAÑAS (INCLUYENDO PROYECTOS)
        # ==========================================
        tab_dash, tab_proyectos, tab_vip, tab_potencial, tab_general = st.tabs(["📊 Dashboard", "📁 Proyectos", "🏆 VIP", "🚀 Alertas", "📋 General"])

        # --- PESTAÑA 0: DASHBOARD ---
        with tab_dash:
            st.markdown("### 📈 Desempeño Histórico 2026")
            col_m, col_u = st.columns(2)
            with col_m:
                st.markdown("#### 🇲🇽 Mercado Nacional (MXN)")
                m1, m2 = st.columns(2)
                m1.metric("✅ Ganado MXN", f"${mxn_ganado:,.2f}")
                m2.metric("❌ Perdido MXN", f"${mxn_perdido:,.2f}")
                st.metric("⏳ En Proceso MXN", f"${mxn_proceso:,.2f}")
            with col_u:
                st.markdown("#### 🇺🇸 Mercado Extranjero (USD)")
                u1, u2 = st.columns(2)
                u1.metric("✅ Ganado USD", f"${usd_ganado:,.2f}")
                u2.metric("❌ Perdido USD", f"${usd_perdido:,.2f}")
                st.metric("⏳ En Proceso USD", f"${usd_proceso:,.2f}")

        # --- PESTAÑA 1: PROYECTOS (CONSOLIDADO) ---
        with tab_proyectos:
            st.markdown("### 📁 Estatus Consolidado por Proyectos (Histórico)")
            if 'ID_Proyecto' in df.columns:
                df_proyectos = df.dropna(subset=['ID_Proyecto']).copy()
                if not df_proyectos.empty:
                    def evaluar_estatus_proyecto(estatus_lista):
                        estatus_str = " ".join(estatus_lista).upper()
                        if "GANAD" in estatus_str: return "✅ GANADO"
                        elif "PROCESO" in estatus_str: return "⏳ EN PROCESO"
                        else: return "❌ PERDIDO/CANCELADO"

                    # Agrupamos por proyecto
                    g_cols = ['ID_Proyecto', 'Cliente']
                    if 'Descripcion_Proyecto' in df_proyectos.columns: g_cols.append('Descripcion_Proyecto')
                    
                    resumen_proyectos = df_proyectos.groupby(g_cols).agg(
                        Cotizaciones_Asociadas=('Cotización', 'count'),
                        MXN_Total=('Monto_MXN', 'sum'),
                        USD_Total=('Monto_USD', 'sum'),
                        Estatus_General=('Estatus', evaluar_estatus_proyecto)
                    ).reset_index()
                    
                    resumen_proyectos = resumen_proyectos.sort_values(by='MXN_Total', ascending=False)
                    st.dataframe(resumen_proyectos.style.format({'MXN_Total': '${:,.2f}', 'USD_Total': '${:,.2f}'}), use_container_width=True)
                else:
                    st.info("Ninguna cotización tiene un número de proyecto asignado.")
            else:
                st.info("El archivo CSV no contiene la columna 'PROYECTO'.")

        # --- PESTAÑA 2: VIP (ACTIVAS) ---
        with tab_vip:
            if not df_vip.empty:
                lista_vip = ["Todos"] + sorted(df_vip['Cliente'].unique().tolist())
                sel_vip = st.selectbox("Filtrar VIP:", lista_vip, key="f_vip")
                df_mostrar_vip = df_vip if sel_vip == "Todos" else df_vip[df_vip['Cliente'] == sel_vip]
                st.data_editor(df_mostrar_vip[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel_vip}")

        # --- PESTAÑA 3: EMERGENTES (ACTIVAS) ---
        with tab_potencial:
            if not df_potencial.empty:
                lista_pot = ["Todos"] + sorted(df_potencial['Cliente'].unique().tolist())
                sel_pot = st.selectbox("Filtrar Emergentes:", lista_pot, key="f_pot")
                df_mostrar_pot = df_potencial if sel_pot == "Todos" else df_potencial[df_potencial['Cliente'] == sel_pot]
                st.data_editor(df_mostrar_pot[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel_pot}")

        # --- PESTAÑA 4: GENERAL (ACTIVAS) ---
        with tab_general:
            if not df_general.empty:
                lista_gral = ["Todos"] + sorted(df_general['Cliente'].unique().tolist())
                sel_gral = st.selectbox("Filtrar Base:", lista_gral, key="f_gral")
                df_mostrar_gral = df_general if sel_gral == "Todos" else df_general[df_general['Cliente'] == sel_gral]
                st.data_editor(df_mostrar_gral[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel_gral}")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.write("Por favor sube tu archivo CSV histórico de Scott para empezar.")
