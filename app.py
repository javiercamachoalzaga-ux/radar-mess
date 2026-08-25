import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

# ==========================================
# INICIALIZACIÓN DE MEMORIA PARA AGENDA
# ==========================================
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=['ID_Tarea', 'Fecha', 'Cliente', 'ID_Proyecto', 'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN', 'Tipo_Accion', 'Completado'])

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Montserrat', sans-serif !important; 
    }
    
    /* Header Corporativo */
    .titulo-radar {
        font-size: 42px; 
        font-weight: 900;
        color: #003a70;
        margin-bottom: -5px;
        letter-spacing: -1px;
        text-transform: uppercase;
    }
    .subtitulo { 
        font-size: 16px; 
        color: #555555; 
        margin-bottom: 30px; 
        font-weight: 600; 
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* Tarjetas de Métricas */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px 20px;
        border-radius: 8px;
        border-left: 5px solid #003a70;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #7f8c8d !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #2c3e50 !important;
    }

    /* Pestañas (Tabs) Estilizadas */
    button[role="tab"] {
        font-weight: 700 !important;
        font-size: 14px !important;
        padding-bottom: 10px !important;
        text-transform: uppercase;
        color: #7f8c8d !important;
    }
    button[role="tab"][aria-selected="true"] {
        color: #003a70 !important;
        border-bottom-color: #003a70 !important;
    }
    
    /* === CORRECCIÓN DE CONTRASTE EN SIDEBAR === */
    [data-testid="stSidebar"] {
        background-color: #f4f6f7 !important;
        border-right: 1px solid #e0e0e0;
    }
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
        color: #003a70 !important;
        font-weight: 600;
    }
    .stTextInput input {
        color: #000000 !important;
        background-color: #ffffff !important;
        border: 1px solid #b2bec3 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def check_password():
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral para acceder al sistema.")
    st.stop()

try:
    st.sidebar.image("logo mess 1.jpg", use_container_width=True)
except:
    pass

st.markdown('<div class="titulo-radar">Radar Comercial</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia de Cierres Diarios y Proyectos Vivos</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto", type=["csv"])

if archivo_cargado is not None:
    try:
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        df_clean['Cotizacion'] = buscar_col(["COTIZACION"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn_total = pd.Series([0.0] * len(df_raw))
        monto_usd_total = pd.Series([0.0] * len(df_raw))

        for col in df_raw.columns:
            nombre_limpio = str(col).upper().strip()
            if nombre_limpio == "VALOR" or nombre_limpio.startswith("VALOR."):
                temp_mxn = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                temp_usd = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
                monto_mxn_total += temp_mxn
                monto_usd_total += temp_usd

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total

        df = df_clean

        # FILTRO ESTRICTO
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
        if 'Area' not in df.columns: df['Area'] = 'SIN ÁREA'
        df['Area'] = df['Area'].fillna('SIN ÁREA').astype(str).str.strip().str.upper()
        
        if 'Descripcion' not in df.columns: df['Descripcion'] = 'Sin Descripción'
        df['Descripcion'] = df['Descripcion'].fillna('Sin Descripción').astype(str)
        
        df = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        
        # Valor interno unicamente para ordenar jerarquias (no se muestra al usuario)
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)

        # ==========================================
        # CLASIFICACIÓN GLOBAL POR UNIDAD DE NEGOCIO Y VIP
        # ==========================================
        def categorizar_unidad(area):
            area_upper = str(area).upper()
            if any(kw in area_upper for kw in ["ALTA GAMA", "EQUIPO", "CMM", "ZEISS", "SCANNER", "SCANTECH", "KREON", "BATY", "MITUTOYO"]): 
                return "ALTA GAMA"
            elif any(kw in area_upper for kw in ["LABORATORIO", "CALIBRACIÓN", "CALIBRACION", "SERVICIO", "DIMENSIONAL"]): 
                return "LABORATORIOS"
            else: 
                return "PRODUCTOS" 

        df['Unidad_Presupuesto'] = df['Area'].apply(categorizar_unidad)
        
        top_10_vip = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        df['Clasificacion_VIP'] = df['Cliente'].apply(lambda c: "VIP" if any(m in c.upper() for m in top_10_vip) else "Normal")

        # ==========================================
        # FILTROS TÁCTICOS (MENÚ LATERAL)
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("Filtros Tácticos")
        
        busqueda_proyecto = st.sidebar.text_input("Buscar ID de Proyecto o Cliente:", placeholder="Ej. 111822 o SAFRAN")
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]

        max_monto = float(df['Peso_Interno_Orden'].max()) if not df.empty else 1000000.0
        if pd.isna(max_monto) or max_monto == 0: max_monto = 100000.0
        
        rango_monto = st.sidebar.slider("Rango de Monto Interno", 
                                      min_value=0.0, 
                                      max_value=max_monto, 
                                      value=(0.0, max_monto), 
                                      step=5000.0)

        tipo_filtro_fecha = st.sidebar.selectbox("Filtrar por Fecha:", ["Sin Filtro", "Fecha de Creación", "Fecha de Cierre"])
        
        df = df[(df['Peso_Interno_Orden'] >= rango_monto[0]) & (df['Peso_Interno_Orden'] <= rango_monto[1])]

        if tipo_filtro_fecha != "Sin Filtro":
            col_fecha = 'Fecha_Creacion_DT' if tipo_filtro_fecha == "Fecha de Creación" else 'Fecha_Cierre_DT'
            min_date = df[col_fecha].min()
            max_date = df[col_fecha].max()
            
            if pd.notna(min_date) and pd.notna(max_date):
                fecha_rango = st.sidebar.date_input("Selecciona el rango:", [min_date.date(), max_date.date()])
                if len(fecha_rango) == 2:
                    f_ini, f_fin = fecha_rango
                    mask = (df[col_fecha].dt.date >= f_ini) & (df[col_fecha].dt.date <= f_fin)
                    incluir_vacios = st.sidebar.checkbox(f"Incluir registros sin {tipo_filtro_fecha}", value=True)
                    if incluir_vacios: df = df[mask | df[col_fecha].isna()]
                    else: df = df[mask]
            else:
                st.sidebar.warning("No hay registros válidos para el filtro de fecha.")

        st.sidebar.divider()
        st.sidebar.header("Tubería Filtrada")
        st.sidebar.metric("Total USD en Proceso", f"${df['Monto_USD'].sum():,.2f}")
        st.sidebar.metric("Total MXN en Proceso", f"${df['Monto_MXN'].sum():,.2f}")

        mes_actual = pd.Timestamp.now().month
        anio_actual = pd.Timestamp.now().year
        meses_es = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 
                    7:"JULIO", 8:"AGOSTO", 9:"SEPTIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
        nombre_mes = meses_es.get(mes_actual, "MES ACTUAL")

        # ==========================================
        # RENDERIZADO DE PESTAÑAS MAESTRAS
        # ==========================================
        tab_finanzas, tab_ejecucion = st.tabs(["Inteligencia Financiera", "Centro de Ejecucion"])

        # ==========================================
        # PESTAÑA 1: INTELIGENCIA FINANCIERA
        # ==========================================
        with tab_finanzas:
            st.markdown("### Dashboard de Cumplimiento Mensual")
            
            BUDGET_ALTA_GAMA = 28000.00
            BUDGET_LABORATORIOS = 15000.00
            BUDGET_PRODUCTOS = 45000.00
            
            df_mes_tracker = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & 
                                (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
            
            pipe_alta_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_USD'].sum()
            pipe_alta_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_MXN'].sum()
            
            pipe_labs_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_USD'].sum()
            pipe_labs_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_MXN'].sum()
            
            pipe_prod_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_USD'].sum()
            pipe_prod_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_MXN'].sum()
            
            datos_budget_usd = {
                'Unidad': ['ALTA GAMA', 'LABORATORIOS', 'PRODUCTOS'],
                'Radar USD': [pipe_alta_usd, pipe_labs_usd, pipe_prod_usd],
                'Meta USD': [BUDGET_ALTA_GAMA, BUDGET_LABORATORIOS, BUDGET_PRODUCTOS]
            }
            df_chart_usd = pd.DataFrame(datos_budget_usd).set_index('Unidad')

            col_b1, col_b2, col_b3 = st.columns([1.5, 1, 1])

            with col_b1:
                st.markdown("#### Progreso contra Presupuesto USD")
                st.bar_chart(df_chart_usd, use_container_width=True)
                
            with col_b2:
                 st.markdown("#### Radar Capturado USD")
                 st.metric("Alta Gama (Meta: $28K)", f"${pipe_alta_usd:,.0f} USD")
                 st.metric("Laboratorios (Meta: $15K)", f"${pipe_labs_usd:,.0f} USD")
                 st.metric("Productos (Meta: $45K)", f"${pipe_prod_usd:,.0f} USD")
                 
            with col_b3:
                 st.markdown("#### Radar Adicional MXN")
                 st.metric("Alta Gama", f"${pipe_alta_mxn:,.0f} MXN")
                 st.metric("Laboratorios", f"${pipe_labs_mxn:,.0f} MXN")
                 st.metric("Productos", f"${pipe_prod_mxn:,.0f} MXN")
                 
            st.divider()

            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                st.markdown("### Concentracion de Capital: Cuentas VIP")
                df_vip_finanzas = df[df['Clasificacion_VIP'] == "VIP"]
                if not df_vip_finanzas.empty:
                    st.bar_chart(df_vip_finanzas.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Cliente'), use_container_width=True)
                else:
                    st.info("No hay cotizaciones vivas para cuentas VIP.")

            with col_f2:
                st.markdown("### Distribucion por Unidades de Negocio")
                if not df.empty and 'Area' in df.columns:
                    resumen_area = df.groupby('Area')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Area')
                    st.bar_chart(resumen_area, use_container_width=True)
                else:
                    st.info("No se encontro informacion de Areas.")

        # ==========================================
        # PESTAÑA 2: CENTRO DE EJECUCIÓN (PLAN DE ACCIÓN)
        # ==========================================
        with tab_ejecucion:
            st.markdown("### Segmentacion Estrategica del Mes Corriente")
            st.caption(f"Proyectos clasificados por nivel de prioridad para cierre en {nombre_mes} {anio_actual}.")
            
            if not df.empty:
                df_mes_plan = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & 
                                 (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
                
                if not df_mes_plan.empty:
                    # Conteo de volumen para el algoritmo cruzado
                    conteo_cotizaciones = df_mes_plan.groupby('Cliente')['Cotizacion'].nunique().reset_index()
                    conteo_cotizaciones.rename(columns={'Cotizacion': 'Num_Cotizaciones'}, inplace=True)
                    df_mes_plan = pd.merge(df_mes_plan, conteo_cotizaciones, on='Cliente', how='left')

                    # Algoritmo Integrado de Prioridad
                    def clasificar_prioridad(fila):
                        if fila['Clasificacion_VIP'] == "VIP" or fila['Num_Cotizaciones'] >= 3 or fila['Monto_USD'] >= 10000 or fila['Monto_MXN'] >= 190000:
                            return "ALTA (Cierre Estrategico)"
                        elif (fila['Monto_USD'] <= 2500 and fila['Monto_MXN'] <= 45000) and fila['Num_Cotizaciones'] == 1:
                            return "BAJA (Mantenimiento)"
                        else:
                            return "MEDIA (Desarrollo Tactico)"

                    df_mes_plan['Nivel_Prioridad'] = df_mes_plan.apply(clasificar_prioridad, axis=1)
                    
                    # Preparacion de datos visuales
                    df_mes_plan['Monto USD'] = df_mes_plan['Monto_USD'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                    df_mes_plan['Monto MXN'] = df_mes_plan['Monto_MXN'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                    
                    columnas_mostrar = ['Cliente', 'Descripcion', 'Monto USD', 'Monto MXN', 'ID_Proyecto', 'Num_Cotizaciones']
                    
                    df_alta = df_mes_plan[df_mes_plan['Nivel_Prioridad'] == "ALTA (Cierre Estrategico)"].sort_values(by='Peso_Interno_Orden', ascending=False)
                    df_media = df_mes_plan[df_mes_plan['Nivel_Prioridad'] == "MEDIA (Desarrollo Tactico)"].sort_values(by='Peso_Interno_Orden', ascending=False)
                    df_baja = df_mes_plan[df_mes_plan['Nivel_Prioridad'] == "BAJA (Mantenimiento)"].sort_values(by='Peso_Interno_Orden', ascending=False)

                    st.markdown("#### Prioridad Alta (Enfoque de Cierre e Ingreso Maximo)")
                    if not df_alta.empty: st.dataframe(df_alta[columnas_mostrar], hide_index=True, use_container_width=True)
                    else: st.info("Sin proyectos de alta prioridad para este mes.")

                    st.markdown("#### Prioridad Media (Maduracion Tactica)")
                    if not df_media.empty: st.dataframe(df_media[columnas_mostrar], hide_index=True, use_container_width=True)
                    else: st.info("Sin proyectos de prioridad media para este mes.")

                    st.markdown("#### Prioridad Baja (Seguimiento de Volumen)")
                    if not df_baja.empty: st.dataframe(df_baja[columnas_mostrar], hide_index=True, use_container_width=True)
                    else: st.info("Sin proyectos de prioridad baja para este mes.")
                else:
                    st.info("No tienes cotizaciones con fecha de cierre registrada para el mes en curso.")
            else:
                st.info("Ajusta los filtros o carga tu archivo para visualizar las prioridades.")
            
            st.divider()
            
            # --- PLANIFICADOR DE ACTIVIDADES (VISIBLE Y DIRECTO) ---
            st.markdown("### Planificador de Agenda Diario")
            
            with st.form("form_agenda_radar"):
                col_f1, col_f2, col_f3 = st.columns([2.5, 1, 1])
                
                with col_f1:
                    if not df_mes_plan.empty:
                        # Etiqueta enriquecida con Descripcion Corta para seleccion rapida
                        df_mes_plan['Desc_Corta'] = df_mes_plan['Descripcion'].astype(str).str[:30] + "..."
                        df_mes_plan['Etiqueta_Select'] = df_mes_plan['Nivel_Prioridad'].str.split().str[0] + " | " + df_mes_plan['Cliente'].astype(str) + " | " + df_mes_plan['Desc_Corta'] + " | ID: " + df_mes_plan['ID_Proyecto'].astype(str)
                        
                        df_vivos_ordenados = df_mes_plan.sort_values(by=['Nivel_Prioridad', 'Peso_Interno_Orden'], ascending=[True, False])
                        lista_clientes = df_vivos_ordenados['Etiqueta_Select'].unique().tolist()
                    else:
                        lista_clientes = ["Sin proyectos validos"]
                        
                    cliente_sel = st.selectbox("1. Selecciona el Proyecto a Atender:", lista_clientes)
                    
                with col_f2:
                    accion_sel = st.selectbox("2. Tipo de Accion:", ["Visita Presencial", "Llamada Consultiva", "Correo y Cotizacion", "Cierre y Negociacion"])
                    
                with col_f3:
                    fecha_sel = st.date_input("3. Fecha de Ejecucion:", pd.Timestamp.now().date())
                    
                btn_agendar = st.form_submit_button("Agendar Accion")
                
                if btn_agendar and cliente_sel != "Sin proyectos validos":
                    id_proy_str = cliente_sel.split("ID: ")[1].strip()
                    fila_proy = df_mes_plan[df_mes_plan['ID_Proyecto'].astype(str) == id_proy_str].iloc[0]
                    
                    nueva_tarea = pd.DataFrame([{
                        'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1, 10000),
                        'Fecha': fecha_sel,
                        'Cliente': fila_proy['Cliente'],
                        'ID_Proyecto': fila_proy['ID_Proyecto'],
                        'Unidad_Presupuesto': fila_proy['Unidad_Presupuesto'],
                        'Monto_USD': fila_proy['Monto_USD'],
                        'Monto_MXN': fila_proy['Monto_MXN'],
                        'Tipo_Accion': accion_sel,
                        'Completado': False
                    }])
                    st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    st.success("Actividad registrada en la ruta.")
                    
            st.divider()

            # --- DASHBOARD DIARIO DE RUTAS ---
            st.markdown("#### Tablero de Ejecucion Diaria")
            fecha_vista = st.date_input("Seleccionar dia a visualizar:", pd.Timestamp.now().date(), key="vista_fecha_agenda")
            
            for col_req in ['ID_Proyecto', 'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN']:
                if col_req not in st.session_state.agenda_radar.columns:
                    st.session_state.agenda_radar[col_req] = None
                    
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            
            if not df_dia.empty and df_dia['Unidad_Presupuesto'].notna().all():
                df_dia['Peso_Temporal'] = df_dia['Monto_MXN'] + (df_dia['Monto_USD'] * 19.50)
                df_dia = df_dia.sort_values(by=['Peso_Temporal'], ascending=[False])
                
                total_tareas = len(df_dia)
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Valor USD del Dia", f"${df_dia['Monto_USD'].sum():,.0f} USD")
                col_m2.metric("Valor MXN del Dia", f"${df_dia['Monto_MXN'].sum():,.0f} MXN")
                col_m3.metric("Total Actividades", f"{total_tareas}")
                col_m4.metric("Visitas Criticas", len(df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]))
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                df_mostrar = df_dia[['Completado', 'Unidad_Presupuesto', 'Tipo_Accion', 'Cliente', 'Monto_USD', 'Monto_MXN']].copy()
                df_mostrar['Monto_USD'] = df_mostrar['Monto_USD'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                df_mostrar['Monto_MXN'] = df_mostrar['Monto_MXN'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                df_mostrar = df_mostrar.rename(columns={'Unidad_Presupuesto': 'Unidad', 'Monto_USD': 'USD', 'Monto_MXN': 'MXN'})
                
                proyectos_actualizados = st.data_editor(
                    df_mostrar,
                    hide_index=True,
                    use_container_width=True,
                    key="editor_agenda",
                    column_config={
                        "Completado": st.column_config.CheckboxColumn("Realizado", default=False),
                        "USD": st.column_config.TextColumn("USD", disabled=True),
                        "MXN": st.column_config.TextColumn("MXN", disabled=True),
                        "Unidad": st.column_config.TextColumn("Unidad", disabled=True),
                        "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                        "Tipo_Accion": st.column_config.TextColumn("Accion", disabled=True)
                    }
                )
                
                tareas_completadas = proyectos_actualizados['Completado'].sum()
                for i, idx in enumerate(df_dia.index):
                     st.session_state.agenda_radar.loc[idx, 'Completado'] = proyectos_actualizados.iloc[i]['Completado']
                     
                st.divider()
                progreso = int((tareas_completadas / total_tareas) * 100) if total_tareas > 0 else 0
                st.markdown(f"**Nivel de Avance del Dia: {progreso}%**")
                st.progress(progreso)
                
                if st.button("Depurar actividades finalizadas"):
                    st.session_state.agenda_radar = st.session_state.agenda_radar[~((st.session_state.agenda_radar['Fecha'] == fecha_vista) & (st.session_state.agenda_radar['Completado'] == True))]
                    st.rerun()
            else:
                st.info("Agenda libre. Utiliza el panel superior para programar cuentas.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles de sistema: {e}")
else:
    st.info("Sube el reporte comercial formato CSV para desplegar la inteligencia tactica.")
