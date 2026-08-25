import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# CONFIGURACION DE PAGINA Y ESTILOS
# ==========================================
st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"], table, th, td { font-family: 'Montserrat', sans-serif !important; }
    
    .titulo-radar {
        font-size: 38px; font-weight: 900; color: #003a70;
        margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase;
    }
    .subtitulo { 
        font-size: 15px; color: #555555; margin-bottom: 30px; 
        font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
    }

    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 15px 20px; border-radius: 8px;
        border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important; font-weight: 700 !important;
        color: #7f8c8d !important; text-transform: uppercase;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important;
    }

    button[role="tab"] {
        font-weight: 700 !important; font-size: 14px !important;
        padding-bottom: 10px !important; text-transform: uppercase; color: #7f8c8d !important;
    }
    button[role="tab"][aria-selected="true"] {
        color: #003a70 !important; border-bottom-color: #003a70 !important;
    }
    
    [data-testid="stSidebar"] { background-color: #f4f6f7 !important; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] p, label, h1, h2, h3, span { color: #003a70 !important; font-weight: 600; }
    
    .stDataFrame { font-family: 'Montserrat', sans-serif !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# INICIALIZACION DE MEMORIA PARA AGENDA
# ==========================================
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=['ID_Tarea', 'Fecha', 'Cliente', 'Tipo_Accion', 'Completado'])

# ==========================================
# CONTROL DE ACCESO
# ==========================================
def check_password():
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contrasena", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: 
        return True
    return False

if not check_password():
    st.info("Ingresa tu contrasena en el menu lateral para acceder al sistema.")
    st.stop()

try:
    st.sidebar.image("logo mess 1.jpg", use_container_width=True)
except:
    pass

st.markdown('<div class="titulo-radar">Radar Comercial</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Panel de Control Estrategico y CRM</div>', unsafe_allow_html=True)

# ==========================================
# CARGA Y PROCESAMIENTO DE DATOS
# ==========================================
archivo_cargado = st.sidebar.file_uploader("Subir base de datos (CSV)", type=["csv"])

if archivo_cargado is not None:
    try:
        try:
            df = pd.read_csv(archivo_cargado, encoding='utf-8-sig')
        except UnicodeDecodeError:
            archivo_cargado.seek(0)
            df = pd.read_csv(archivo_cargado, encoding='latin-1')

        # Limpieza de nombres de columnas
        df.columns = df.columns.str.strip()

        # Metricas globales seguras
        monto_mxn_total = 0.0
        monto_usd_total = 0.0

        # Lector automatico de divisas
        if 'Total_MXN' in df.columns:
            df['Total_MXN'] = pd.to_numeric(df['Total_MXN'].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce').fillna(0.0)
            monto_mxn_total = df['Total_MXN'].sum()
            
        if 'Total_USD' in df.columns:
            df['Total_USD'] = pd.to_numeric(df['Total_USD'].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce').fillna(0.0)
            monto_usd_total = df['Total_USD'].sum()

        if 'Cliente' not in df.columns:
            df['Cliente'] = "Cliente Desconocido"
            
        if 'Estatus' not in df.columns:
            df['Estatus'] = "EN PROCESO"
            
        # Filtramos para no mostrar los ganados/perdidos en la prospeccion
        df_activos = df[~df['Estatus'].astype(str).str.upper().isin(['GANADA', 'PERDIDA', 'COMPLETADA', 'FACTURADA'])].copy()

        # ==========================================
        # ESTRUCTURA DE PESTANAS (TABS)
        # ==========================================
        tab_dash, tab_proyectos, tab_vip, tab_plan = st.tabs([
            "Resumen Global", 
            "Directorio de Proyectos", 
            "Clientes VIP", 
            "Plan de Accion"
        ])

        # --- PESTANA 1: RESUMEN GLOBAL ---
        with tab_dash:
            st.markdown("### Metricas del Pipeline Activo")
            col_m1, col_m2 = st.columns(2)
            
            with col_m1:
                st.markdown("#### Objetivo MXN a Cerrar")
                st.metric("Total MXN Activo", f"${monto_mxn_total:,.2f}")
                
            with col_m2:
                st.markdown("#### Objetivo USD a Cerrar")
                st.metric("Total USD Activo", f"${monto_usd_total:,.2f}")

            st.divider()
            st.markdown("#### Distribucion de Cartera por Area")
            if 'Area' in df.columns:
                resumen_area = df_activos.groupby('Area').agg({'Total_MXN': 'sum'}).reset_index()
                st.bar_chart(resumen_area.set_index('Area'))
            else:
                st.info("No se encontro la columna 'Area' para graficar la distribucion.")

        # --- PESTANA 2: PROYECTOS ---
        with tab_proyectos:
            st.markdown("### Base de Datos Activa")
            st.dataframe(df_activos, hide_index=True, use_container_width=True)

        # --- PESTANA 3: CLIENTES VIP ---
        with tab_vip:
            st.markdown("### Cuentas Estrategicas (Top Facturacion)")
            if 'Total_MXN' in df_activos.columns:
                vip_df = df_activos.groupby('Cliente').agg({'Total_MXN': 'sum', 'Total_USD': 'sum'}).reset_index()
                vip_df['Peso_Total'] = vip_df['Total_MXN'] + (vip_df['Total_USD'] * 19.50)
                vip_df = vip_df.sort_values(by='Peso_Total', ascending=False).head(15)
                
                col_v1, col_v2 = st.columns([2, 3])
                with col_v1:
                    st.dataframe(vip_df[['Cliente', 'Total_MXN', 'Total_USD']].style.format({'Total_MXN': '${:,.2f}', 'Total_USD': '${:,.2f}'}), hide_index=True, use_container_width=True)
                with col_v2:
                    st.bar_chart(vip_df.set_index('Cliente')[['Total_MXN', 'Total_USD']])
            else:
                st.info("No hay datos de montos para calcular el rango de clientes VIP.")

        # --- PESTANA 4: PLAN DE ACCION Y AGENDA ---
        with tab_plan:
            st.markdown("### Modulo de Ejecucion Comercial")
            
            # 1. FORMULARIO DE ASIGNACION
            st.markdown("#### Programar Seguimiento")
            
            with st.form("form_agenda_radar"):
                col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
                
                with col_f1:
                    if 'ID_Proyecto' in df_activos.columns:
                        lista_clientes = (df_activos['Cliente'].astype(str) + " (ID: " + df_activos['ID_Proyecto'].astype(str) + ")").unique()
                    else:
                        lista_clientes = df_activos['Cliente'].astype(str).unique()
                        
                    cliente_sel = st.selectbox("1. Selecciona la Cuenta:", lista_clientes)
                    
                with col_f2:
                    accion_sel = st.selectbox("2. Tipo de Accion:", ["Llamada", "Visita Presencial", "Correo Electronico"])
                    
                with col_f3:
                    fecha_sel = st.date_input("3. Fecha Programada:", pd.Timestamp.now().date())
                    
                btn_agendar = st.form_submit_button("Agregar a la Agenda")
                
                if btn_agendar:
                    nueva_tarea = pd.DataFrame([{
                        'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1, 10000),
                        'Fecha': fecha_sel,
                        'Cliente': cliente_sel,
                        'Tipo_Accion': accion_sel,
                        'Completado': False
                    }])
                    st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    st.success("Actividad registrada exitosamente en el calendario.")
                    
            st.divider()
            
            # 2. TABLERO DE CONTROL DIARIO
            st.markdown("#### Planificador de Actividades")
            fecha_vista = st.date_input("Seleccionar dia de ejecucion:", pd.Timestamp.now().date(), key="vista_fecha_agenda")
            
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            
            if not df_dia.empty:
                df_llamadas = df_dia[df_dia['Tipo_Accion'] == "Llamada"]
                df_visitas = df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]
                df_correos = df_dia[df_dia['Tipo_Accion'] == "Correo Electronico"]
                
                total_tareas = len(df_dia)
                tareas_completadas = 0
                
                col_a1, col_a2, col_a3 = st.columns(3)
                
                with col_a1:
                    st.markdown("**Llamadas**")
                    if not df_llamadas.empty:
                        for idx, row in df_llamadas.iterrows():
                            marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                            if marcado: tareas_completadas += 1
                            st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
                    else: st.caption("Sin registros.")
                    
                with col_a2:
                    st.markdown("**Visitas**")
                    if not df_visitas.empty:
                        for idx, row in df_visitas.iterrows():
                            marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                            if marcado: tareas_completadas += 1
                            st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
                    else: st.caption("Sin registros.")
                    
                with col_a3:
                    st.markdown("**Correos**")
                    if not df_correos.empty:
                        for idx, row in df_correos.iterrows():
                            marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                            if marcado: tareas_completadas += 1
                            st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
                    else: st.caption("Sin registros.")
                    
                # BARRA DE PROGRESO
                st.divider()
                progreso = int((tareas_completadas / total_tareas) * 100)
                st.markdown(f"**Nivel de Avance: {progreso}%** ({tareas_completadas} de {total_tareas} cuentas atendidas)")
                st.progress(progreso)
                
                if progreso == 100:
                    st.success("Operacion diaria finalizada con exito.")
                    
                if st.button("Depurar actividades completadas"):
                    st.session_state.agenda_radar = st.session_state.agenda_radar[~((st.session_state.agenda_radar['Fecha'] == fecha_vista) & (st.session_state.agenda_radar['Completado'] == True))]
                    st.rerun()
                    
            else:
                st.info("Sin agenda registrada para esta fecha. Utiliza el panel superior para programar cuentas.")

    except Exception as e:
        st.error(f"Se encontro un problema al leer el archivo. Verifica el formato. Detalle tecnico: {e}")
else:
    st.info("Carga el archivo CSV del sistema para habilitar el Radar Comercial.")
