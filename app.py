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
    .metric-ganada { color: #28a745 !important; }
    .metric-perdida { color: #dc3545 !important; }
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

# 3. Encabezado
st.markdown('<div class="titulo-radar">⚡ Radar Comercial 80/20</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia Táctica y Análisis Histórico 2026</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott (Histórico Completo)", type=["csv"])

if archivo_cargado is not None:
    try:
        # Leemos y limpiamos
        df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
        df.columns = df.columns.str.strip()
        
        # --- NUEVO: CAPTURAMOS EL ESTATUS ---
        traductor = {
            "COTIZACION": "Cotización", "CLIENTE": "Cliente", "VALOR": "Monto_Bruto", 
            "FECHA": "Fecha_Registro", "ESTATUS": "Estatus"
        }
        df = df.rename(columns=lambda x: traductor.get(x, x))
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        
        # Normalizamos el estatus para evitar errores de mayúsculas/minúsculas
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
        df['Valor_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # --- ESCÁNER TOP 10 VIP ---
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        def es_vip(cliente_str):
            cliente_str = cliente_str.upper()
            for marca in top_10:
                if marca in cliente_str: return "⭐ TOP 10"
            return "Normal"
        df['Prioridad'] = df['Cliente'].apply(es_vip)

        # --- CÁLCULO DE HIT RATE Y ESTADÍSTICAS GLOBALES ---
        mxn_ganado = df[df['Estatus'].str.contains('GANAD', na=False)]['Valor_Orden'].sum()
        mxn_perdido = df[df['Estatus'].str.contains('PERDID|CANCELAD', na=False)]['Valor_Orden'].sum()
        mxn_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)]['Valor_Orden'].sum()
        
        total_cerrado = mxn_ganado + mxn_perdido
        hit_rate_real = (mxn_ganado / total_cerrado * 100) if total_cerrado > 0 else 0

        # --- PANEL LATERAL DE PROYECCIÓN ---
        st.sidebar.markdown("---")
        st.sidebar.header("📈 Proyección Comercial")
        st.sidebar.metric("Hit Rate Real Histórico", f"{hit_rate_real:.1f}%", help="Calculado sobre las cotizaciones ya cerradas (Ganadas vs Perdidas).")
        tasa_bateo = st.sidebar.slider("Simulador de Bateo Futuro (%)", min_value=5, max_value=100, value=int(hit_rate_real) if hit_rate_real > 0 else 30, step=5)

        # --- SEMÁFOROS Y ESTRATEGIA (SOLO PARA LO QUE ESTÁ EN PROCESO) ---
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
            monto = fila['Valor_Orden']
            
            if prioridad == "⭐ TOP 10":
                if "🔴" in sla: return "🚨 RIESGO: Visita presencial inmediata. Aclarar dudas técnicas."
                elif "🟡" in sla: return "📞 ALERTA: Llamada consultiva."
                else: return "✉️ SEGUIMIENTO: Correo de presencia."
            else:
                if monto > 15000: return "💼 ALTO VALOR: Visita/Llamada para revisar alcance técnico."
                elif "🔴" in sla: return "⏱️ 80/20: Llamada de 5 min. Descartar rápido si hay bloqueo."
                else: return "📱 CONTACTO: WhatsApp de seguimiento."

        df_activas['Estrategia_Cierre'] = df_activas.apply(generar_estrategia, axis=1)
        df_activas = df_activas.sort_values(by='Valor_Orden', ascending=False)
        cols_vista = ['SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']

        # ==========================================
        # PREPARACIÓN DE LAS BASES DE DATOS ACTIVAS
        # ==========================================
        df_vip = df_activas[df_activas['Prioridad'] == "⭐ TOP 10"].copy()
        
        df_normal = df_activas[df_activas['Prioridad'] == "Normal"].copy()
        ranking_normal = df_normal.groupby('Cliente')['Valor_Orden'].sum().reset_index().sort_values(by='Valor_Orden', ascending=False)
        top_5_nombres = ranking_normal.head(5)['Cliente'].tolist()
        
        df_potencial = df_normal[df_normal['Cliente'].isin(top_5_nombres)].copy()
        df_general = df_normal[~df_normal['Cliente'].isin(top_5_nombres)].copy()

        # ==========================================
        # PESTAÑAS Y RENDERIZADO
        # ==========================================
        tab_dash, tab_vip, tab_potencial, tab_general = st.tabs(["📊 Dashboard Estadístico", "🏆 VIP (Activas)", "🚀 Alertas (Activas)", "📋 General (Activas)"])

        # --- PESTAÑA 0: DASHBOARD HISTÓRICO ---
        with tab_dash:
            st.markdown("### 📈 Desempeño Histórico 2026")
            st.write("Análisis de toda tu tubería de ventas. Los montos combinan MXN y USD (convertidos al tipo de cambio base de 19.50 para la gráfica).")
            
            # Métricas principales
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Cotizado (MXN Eq)", f"${df['Valor_Orden'].sum():,.2f}")
            col2.metric("✅ Ganado", f"${mxn_ganado:,.2f}")
            col3.metric("❌ Perdido/Cancelado", f"${mxn_perdido:,.2f}")
            col4.metric("⏳ En Proceso (Pipeline)", f"${mxn_proceso:,.2f}")
            
            st.markdown("---")
            col_grafica, col_top = st.columns([2, 1])
            
            with col_grafica:
                st.markdown("#### Distribución por Estatus")
                resumen_estatus = df.groupby('Estatus')['Valor_Orden'].sum().reset_index()
                # Gráfica nativa de Streamlit
                st.bar_chart(resumen_estatus.set_index('Estatus'))
            
            with col_top:
                st.markdown("#### Top 5 Clientes Cerrados (Ganados)")
                df_ganados = df[df['Estatus'].str.contains('GANAD', na=False)]
                if not df_ganados.empty:
                    top_ganados = df_ganados.groupby('Cliente')['Valor_Orden'].sum().sort_values(ascending=False).head(5)
                    st.dataframe(top_ganados.reset_index().rename(columns={'Valor_Orden': 'Monto Cerrado'}), use_container_width=True)
                else:
                    st.info("Aún no hay cotizaciones ganadas.")

        # --- PESTAÑA 1: VIP (SOLO ACTIVAS) ---
        with tab_vip:
            if not df_vip.empty:
                lista_vip = ["Todos"] + sorted(df_vip['Cliente'].unique().tolist())
                sel_vip = st.selectbox("Filtrar VIP Activo:", lista_vip, key="f_vip")
                df_mostrar_vip = df_vip if sel_vip == "Todos" else df_vip[df_vip['Cliente'] == sel_vip]
                
                tot_mxn = df_mostrar_vip['Monto_MXN'].sum()
                tot_usd = df_mostrar_vip['Monto_USD'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Pipeline MXN", f"${tot_mxn:,.2f}")
                c2.metric(f"Proyección MXN ({tasa_bateo}%)", f"${tot_mxn * (tasa_bateo/100):,.2f}")
                c3.metric("Pipeline USD", f"${tot_usd:,.2f}")
                c4.metric(f"Proyección USD ({tasa_bateo}%)", f"${tot_usd * (tasa_bateo/100):,.2f}")
                
                st.data_editor(df_mostrar_vip[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel_vip}")
            else:
                st.info("Sin cuentas VIP en proceso.")

        # --- PESTAÑA 2: EMERGENTES (SOLO ACTIVAS) ---
        with tab_potencial:
            if not df_potencial.empty:
                lista_pot = ["Todos"] + sorted(df_potencial['Cliente'].unique().tolist())
                sel_pot = st.selectbox("Filtrar Emergentes Activos:", lista_pot, key="f_pot")
                df_mostrar_pot = df_potencial if sel_pot == "Todos" else df_potencial[df_potencial['Cliente'] == sel_pot]
                
                tot_mxn = df_mostrar_pot['Monto_MXN'].sum()
                tot_usd = df_mostrar_pot['Monto_USD'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Pipeline MXN", f"${tot_mxn:,.2f}")
                c2.metric(f"Proyección MXN ({tasa_bateo}%)", f"${tot_mxn * (tasa_bateo/100):,.2f}")
                c3.metric("Pipeline USD", f"${tot_usd:,.2f}")
                c4.metric(f"Proyección USD ({tasa_bateo}%)", f"${tot_usd * (tasa_bateo/100):,.2f}")
                
                st.data_editor(df_mostrar_pot[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel_pot}")
            else:
                st.info("Sin cuentas emergentes en proceso.")

        # --- PESTAÑA 3: CARTERA GENERAL (SOLO ACTIVAS) ---
        with tab_general:
            if not df_general.empty:
                lista_gral = ["Todos"] + sorted(df_general['Cliente'].unique().tolist())
                sel_gral = st.selectbox("Filtrar Cartera Base Activa:", lista_gral, key="f_gral")
                df_mostrar_gral = df_general if sel_gral == "Todos" else df_general[df_general['Cliente'] == sel_gral]
                
                tot_mxn = df_mostrar_gral['Monto_MXN'].sum()
                tot_usd = df_mostrar_gral['Monto_USD'].sum()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Pipeline MXN", f"${tot_mxn:,.2f}")
                c2.metric(f"Proyección MXN ({tasa_bateo}%)", f"${tot_mxn * (tasa_bateo/100):,.2f}")
                c3.metric("Pipeline USD", f"${tot_usd:,.2f}")
                c4.metric(f"Proyección USD ({tasa_bateo}%)", f"${tot_usd * (tasa_bateo/100):,.2f}")
                
                st.data_editor(df_mostrar_gral[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel_gral}")
            else:
                st.info("No hay más clientes activos en la cartera general.")

    except Exception as e:
        st.error(f"Error al procesar el archivo: Verifica que tu CSV contenga la columna ESTATUS. Detalles: {e}")
else:
    st.write("Por favor sube tu archivo CSV histórico de Scott para empezar a analizar.")
