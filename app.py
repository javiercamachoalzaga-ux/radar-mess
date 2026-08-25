import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

# ==========================================
# INICIALIZACIÓN DE MEMORIA PARA AGENDA
# ==========================================
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=['ID_Tarea', 'Fecha', 'Cliente', 'ID_Proyecto', 'Cotizacion', 'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN', 'Tipo_Accion', 'Descripcion', 'Completado'])

if 'clear_key' not in st.session_state:
    st.session_state.clear_key = 0

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
        # LECTURA ROBUSTA DESDE MEMORIA PARA EVITAR CARACTERES ROTOS EN ESPAÑOL
        contenido_archivo = archivo_cargado.read()
        try:
            df_raw = pd.read_csv(io.BytesIO(contenido_archivo), encoding='latin-1')
        except Exception:
            df_raw = pd.read_csv(io.BytesIO(contenido_archivo), encoding='utf-8')

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

        # FILTRO ESTRICTO Y LIMPIEZA DE CLIENTES
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip().str.upper()
        df = df[df['Cliente'] != 'NAN']
        
        # REGLA: Unificación de ITP e Industrias de Tuberías Aeronáuticas
        df['Cliente'] = df['Cliente'].apply(lambda c: "ITP" if "TUBERIAS AERONAUTICAS" in c or "TUBERÍAS AERONÁUTICAS" in c or "ITP" in c else c)

        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
        if 'Area' not in df.columns: df['Area'] = 'SIN ÁREA'
        df['Area'] = df['Area'].fillna('SIN ÁREA').astype(str).str.strip().str.upper()
        
        if 'Descripcion' not in df.columns: df['Descripcion'] = 'Sin Descripción'
        df['Descripcion'] = df['Descripcion'].fillna('Sin Descripción').astype(str)
        
        if 'Cotizacion' not in df.columns: df['Cotizacion'] = 'S/F'
        df['Cotizacion'] = df['Cotizacion'].fillna('S/F').astype(str)
        
        df = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)

        # ==========================================
        # CLASIFICACIÓN GLOBAL POR UNIDAD DE NEGOCIO
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

        st.sidebar.divider()
        contenedor_agenda_lateral = st.sidebar.container()

        mes_actual = pd.Timestamp.now().month
        anio_actual = pd.Timestamp.now().year
        meses_es = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 
                    7:"JULIO", 8:"AGOSTO", 9:"SEPTIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
        nombre_mes = meses_es.get(mes_actual, "MES ACTUAL")

        # ==========================================
        # RENDERIZADO DE PESTAÑAS MAESTRAS
        # ==========================================
        tab_finanzas, tab_ejecucion, tab_agenda = st.tabs(["Inteligencia Financiera", "Centro de Ejecución", "Agenda de Trabajo"])

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
                st.markdown("### Concentración General de Clientes")
                if not df.empty:
                    st.bar_chart(df.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Cliente'), use_container_width=True)
                else:
                    st.info("Sin registros.")

            with col_f2:
                st.markdown("### Distribución General por Unidades")
                if not df.empty and 'Area' in df.columns:
                    resumen_area = df.groupby('Area')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Area')
                    st.bar_chart(resumen_area, use_container_width=True)
                else:
                    st.info("No se encontró información de Áreas.")

        # ==========================================
        # PESTAÑA 2: CENTRO DE EJECUCIÓN 
        # ==========================================
        lista_global_seleccionados = []
        
        def render_table_interactiva(df_subset, sufijo_clave):
            if df_subset.empty:
                st.info("Sin proyectos en este segmento.")
                return
            
            df_mostrar = df_subset[['Cliente', 'Cotizacion', 'Descripcion', 'Monto_USD', 'Monto_MXN', 'ID_Proyecto', 'Unidad_Presupuesto']].copy()
            df_mostrar.insert(0, 'Seleccionar', False)
            
            df_editado = st.data_editor(
                df_mostrar,
                hide_index=True,
                use_container_width=True,
                key=f"tabla_{sufijo_clave}_{st.session_state.clear_key}",
                column_config={
                    "Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False),
                    "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                    "Cotizacion": st.column_config.TextColumn("Cotización", disabled=True),
                    "Descripcion": st.column_config.TextColumn("Descripción", disabled=True),
                    "Monto_USD": st.column_config.NumberColumn("Monto USD", format="$%.2f", disabled=True),
                    "Monto_MXN": st.column_config.NumberColumn("Monto MXN", format="$%.2f", disabled=True),
                    "ID_Proyecto": st.column_config.TextColumn("ID Proyecto", disabled=True),
                    "Unidad_Presupuesto": st.column_config.TextColumn("Unidad", disabled=True)
                }
            )
            
            seleccion = df_editado[df_editado['Seleccionar'] == True]
            if not seleccion.empty:
                lista_global_seleccionados.append(seleccion)

        with tab_ejecucion:
            st.markdown("### Estructura de Cierre del Mes Corriente")
            st.caption(f"Proyectos clasificados para cierre en {nombre_mes} {anio_actual}. Sin duplicados entre segmentos.")
            
            if not df.empty:
                df_mes_plan = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & 
                                 (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
                
                if not df_mes_plan.empty:
                    # 1. CUENTA CLAVE: Mayor volumen de cotizaciones y mayor monto cotizado en la plantilla
                    resumen_cc = df_mes_plan.groupby('Cliente').agg({
                        'Cotizacion': 'nunique',
                        'Peso_Interno_Orden': 'sum'
                    }).reset_index()
                    resumen_cc = resumen_cc.sort_values(by=['Cotizacion', 'Peso_Interno_Orden'], ascending=[False, False])
                    
                    cliente_clave_top = resumen_cc.iloc[0]['Cliente'] if not resumen_cc.empty else ""
                    
                    df_cuenta_clave = df_mes_plan[df_mes_plan['Cliente'] == cliente_clave_top].copy()
                    df_remanente_1 = df_mes_plan[df_mes_plan['Cliente'] != cliente_clave_top].copy()
                    
                    st.markdown(f"#### CUENTA CLAVE (Máximo Volumen y Monto Cotizado: {cliente_clave_top})")
                    if not df_cuenta_clave.empty:
                        render_table_interactiva(df_cuenta_clave, "cc")
                    else:
                        st.info("No hay cuentas bajo el criterio de Cuenta Clave este mes.")
                        
                    st.divider()

                    # 2. TOP 10 CORPORATIVO
                    top_10_fijo = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
                    
                    # Removemos dinámicamente de la lista maestra la raíz del cliente clave, para no duplicarlo
                    top_10_filtrado = [marca for marca in top_10_fijo if marca not in cliente_clave_top]
                    
                    # Motor de Búsqueda Flexible para atrapar clientes como "CNH INDUSTRIAL" usando la raíz "CNH"
                    def es_top_10(nombre_cliente):
                        for marca in top_10_filtrado:
                            if marca in nombre_cliente:
                                return True
                        return False
                    
                    if not df_remanente_1.empty:
                        df_remanente_1['Es_Top10'] = df_remanente_1['Cliente'].apply(es_top_10)
                        df_top = df_remanente_1[df_remanente_1['Es_Top10']].copy()
                        df_remanente_2 = df_remanente_1[~df_remanente_1['Es_Top10']].copy()
                    else:
                        df_top = pd.DataFrame()
                        df_remanente_2 = pd.DataFrame()

                    # 3 y 4. 80/20 Y DESARROLLO
                    if not df_remanente_2.empty:
                        def es_8020(fila):
                            return fila['Monto_USD'] > 2500 or fila['Monto_MXN'] > 50000
                        
                        df_remanente_2['Es_8020'] = df_remanente_2.apply(es_8020, axis=1)
                        df_8020 = df_remanente_2[df_remanente_2['Es_8020']].copy()
                        df_desarrollo = df_remanente_2[~df_remanente_2['Es_8020']].copy()
                    else:
                        df_8020 = pd.DataFrame()
                        df_desarrollo = pd.DataFrame()

                    def renderizar_subpestanas(df_datos, prefijo):
                        tab_a, tab_l, tab_p = st.tabs(["Alta Gama", "Laboratorios", "Productos"])
                        with tab_a:
                            render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'ALTA GAMA'], f"{prefijo}_ag")
                        with tab_l:
                            render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'LABORATORIOS'], f"{prefijo}_lb")
                        with tab_p:
                            render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'PRODUCTOS'], f"{prefijo}_pr")

                    st.markdown("#### TOP 10 (Cuentas Estratégicas Corporativas)")
                    if not df_top.empty: renderizar_subpestanas(df_top, "top")
                    else: st.info("Sin proyectos en segmento TOP 10.")
                    
                    st.markdown("#### 80/20 (Soporte Táctico)")
                    if not df_8020.empty: renderizar_subpestanas(df_8020, "8020")
                    else: st.info("Sin proyectos en segmento 80/20.")
                    
                    st.markdown("#### DESARROLLO (Siembra a Futuro)")
                    if not df_desarrollo.empty: renderizar_subpestanas(df_desarrollo, "des")
                    else: st.info("Sin proyectos en segmento Desarrollo.")

                else:
                    st.info("No tienes cotizaciones con fecha de cierre registrada para el mes en curso.")
            else:
                st.info("Ajusta los filtros o carga tu archivo para visualizar las prioridades.")

        # ==========================================
        # GESTIÓN RÁPIDA DE AGENDA (BARRA LATERAL)
        # ==========================================
        with contenedor_agenda_lateral:
            st.header("Programación de Ruta")
            
            if lista_global_seleccionados:
                df_seleccion_final = pd.concat(lista_global_seleccionados, ignore_index=True)
                total_seleccionados = len(df_seleccion_final)
                
                st.info(f"Proyectos seleccionados: {total_seleccionados}")
                
                accion_lote = st.selectbox("Acción a ejecutar:", ["Visita Presencial", "Llamada Consultiva", "Correo y Cotización", "Cierre y Negociación"])
                fecha_lote = st.date_input("Fecha programada:", pd.Timestamp.now().date())
                
                if st.button("Agendar Seleccionados"):
                    for _, row in df_seleccion_final.iterrows():
                        nueva_tarea = pd.DataFrame([{
                            'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1, 10000),
                            'Fecha': fecha_lote,
                            'Cliente': row['Cliente'],
                            'ID_Proyecto': row['ID_Proyecto'],
                            'Cotizacion': row['Cotizacion'],
                            'Unidad_Presupuesto': row['Unidad_Presupuesto'],
                            'Monto_USD': row['Monto_USD'],
                            'Monto_MXN': row['Monto_MXN'],
                            'Tipo_Accion': accion_lote,
                            'Descripcion': row['Descripcion'],
                            'Completado': False
                        }])
                        st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    
                    st.success("Actividades agregadas exitosamente a la agenda.")
                    st.session_state.clear_key += 1
                    st.rerun()
            else:
                st.info("Selecciona uno o múltiples proyectos en el Centro de Ejecución para programarlos en tu agenda.")

        # ==========================================
        # PESTAÑA 3: AGENDA DE TRABAJO (FICHA EJECUTIVA DE NEGOCIACIÓN)
        # ==========================================
        with tab_agenda:
            st.markdown("### Tablero de Ejecución Diaria e Inteligencia Comercial")
            fecha_vista = st.date_input("Seleccionar día a visualizar:", pd.Timestamp.now().date(), key="vista_fecha_agenda")
            
            for col_req in ['ID_Proyecto', 'Cotizacion', 'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN', 'Descripcion']:
                if col_req not in st.session_state.agenda_radar.columns:
                    st.session_state.agenda_radar[col_req] = None
                    
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            
            if not df_dia.empty and df_dia['Unidad_Presupuesto'].notna().all():
                df_dia['Peso_Temporal'] = df_dia['Monto_MXN'] + (df_dia['Monto_USD'] * 19.50)
                df_dia = df_dia.sort_values(by=['Peso_Temporal'], ascending=[False])
                
                total_tareas = len(df_dia)
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Valor USD del Día", f"${df_dia['Monto_USD'].sum():,.0f} USD")
                col_m2.metric("Valor MXN del Día", f"${df_dia['Monto_MXN'].sum():,.0f} MXN")
                col_m3.metric("Total Actividades", f"{total_tareas}")
                col_m4.metric("Visitas Críticas", len(df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]))
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                df_mostrar = df_dia[['Completado', 'Unidad_Presupuesto', 'Tipo_Accion', 'Cliente', 'Cotizacion', 'Monto_USD', 'Monto_MXN']].copy()
                df_mostrar['Monto_USD'] = df_mostrar['Monto_USD'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                df_mostrar['Monto_MXN'] = df_mostrar['Monto_MXN'].apply(lambda x: f"${x:,.2f}" if x > 0 else "-")
                df_mostrar = df_mostrar.rename(columns={'Unidad_Presupuesto': 'Unidad', 'Cotizacion': 'Cotización', 'Monto_USD': 'USD', 'Monto_MXN': 'MXN'})
                
                proyectos_actualizados = st.data_editor(
                    df_mostrar,
                    hide_index=True,
                    use_container_width=True,
                    key="editor_agenda_final",
                    column_config={
                        "Completado": st.column_config.CheckboxColumn("Realizado", default=False),
                        "USD": st.column_config.TextColumn("USD", disabled=True),
                        "MXN": st.column_config.TextColumn("MXN", disabled=True),
                        "Unidad": st.column_config.TextColumn("Unidad", disabled=True),
                        "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                        "Cotización": st.column_config.TextColumn("Cotización", disabled=True),
                        "Tipo_Accion": st.column_config.TextColumn("Acción", disabled=True)
                    }
                )
                
                tareas_completadas = proyectos_actualizados['Completado'].sum()
                for i, idx in enumerate(df_dia.index):
                     st.session_state.agenda_radar.loc[idx, 'Completado'] = proyectos_actualizados.iloc[i]['Completado']
                     
                st.divider()
                
                # --- MÓDULO DE INTELIGENCIA COMERCIAL ---
                st.markdown("### Ficha Ejecutiva y Memorándum de Negociación")
                st.caption("Selecciona una cuenta de tu agenda para generar la minuta de revisión directiva o el correo formal de seguimiento.")
                
                clientes_dia_lista = df_dia['Cliente'].unique().tolist()
                cliente_ficha = st.selectbox("Seleccionar cuenta:", clientes_dia_lista)
                
                if cliente_ficha:
                    df_cliente_seleccion = df_mes_plan[df_mes_plan['Cliente'] == cliente_ficha]
                    total_cotiz_cliente = len(df_cliente_seleccion)
                    suma_usd_cli = df_cliente_seleccion['Monto_USD'].sum()
                    suma_mxn_cli = df_cliente_seleccion['Monto_MXN'].sum()
                    
                    tipo_accion_cli = df_dia[df_dia['Cliente'] == cliente_ficha]['Tipo_Accion'].iloc[0]
                    
                    if "Correo" in tipo_accion_cli:
                        st.markdown("#### Borrador de Correo Ejecutivo de Seguimiento")
                        cuerpo_correo = f"""Estimados señores de {cliente_ficha},

Espero que se encuentren muy bien.

Nos ponemos en contacto desde MESS Servicios Metrológicos para dar un seguimiento puntual a las cotizaciones que actualmente tenemos en proceso con ustedes, las cuales representan un valor estratégico conjunto de ${suma_usd_cli:,.2f} USD y ${suma_mxn_cli:,.2f} MXN, abarcando un total de {total_cotiz_cliente} requerimientos vigentes.

Para nosotros es fundamental asegurar que las propuestas de nuestros equipos y servicios se alineen perfectamente con sus expectativas técnicas y de arranque. Quedamos a su entera disposición para coordinar una revisión detallada que permita agilizar la liberación de sus órdenes de compra.

Agradecemos de antemano su confianza y excelente disposición.

Atentamente,
Asesor Comercial / Ejecutivo de Desarrollo de Negocios
MESS Servicios Metrológicos"""
                        st.text_area("Copiable al portapapeles:", cuerpo_correo, height=220)
                    else:
                        st.markdown("#### Ficha Gerencial de Negociación (Memorándum)")
                        st.markdown(f"**Cuenta:** {cliente_ficha}")
                        st.markdown(f"**Volumen Activo en el Mes:** {total_cotiz_cliente} cotizaciones en proceso")
                        st.markdown(f"**Impacto Económico Consolidado:** ${suma_usd_cli:,.2f} USD | ${suma_mxn_cli:,.2f} MXN")
                        
                        st.markdown("---")
                        st.markdown("**Desglose Técnico y Estatus de Partidas:**")
                        for idx_sub, row_sub in df_cliente_seleccion.iterrows():
                            div_str = f"${row_sub['Monto_USD']:,.2f} USD" if row_sub['Monto_USD'] > 0 else f"${row_sub['Monto_MXN']:,.2f} MXN"
                            cot_folio = row_sub['Cotizacion'] if pd.notna(row_sub['Cotizacion']) else "S/F"
                            st.markdown(f"- **Cotización Folio: {cot_folio}** | Proyecto ID: {row_sub['ID_Proyecto']} | Área: *{row_sub['Unidad_Presupuesto']}* | Monto: {div_str}")
                            st.markdown(f"  *Alcance:* {row_sub['Descripcion']}")
                            st.markdown("")

                st.divider()
                progreso = int((tareas_completadas / total_tareas) * 100) if total_tareas > 0 else 0
                st.markdown(f"**Nivel de Avance del Día: {progreso}%**")
                st.progress(progreso)
                
                if st.button("Depurar actividades finalizadas"):
                    st.session_state.agenda_radar = st.session_state.agenda_radar[~((st.session_state.agenda_radar['Fecha'] == fecha_vista) & (st.session_state.agenda_radar['Completado'] == True))]
                    st.rerun()
            else:
                st.info("Agenda libre para este día. Utiliza el Centro de Ejecución para programar cuentas.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles de sistema: {e}")
else:
    st.info("Sube el reporte comercial formato CSV para desplegar la inteligencia táctica.")
