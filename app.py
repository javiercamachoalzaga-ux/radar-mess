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
    
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo-radar { font-size: 42px; font-weight: 900; color: #003a70; margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 16px; color: #555555; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }

    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px 20px; border-radius: 8px;
        border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #7f8c8d !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important; }

    button[role="tab"] { font-weight: 700 !important; font-size: 14px !important; padding-bottom: 10px !important; text-transform: uppercase; color: #7f8c8d !important; }
    button[role="tab"][aria-selected="true"] { color: #003a70 !important; border-bottom-color: #003a70 !important; }
    
    [data-testid="stSidebar"] { background-color: #f4f6f7 !important; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] span {
        color: #003a70 !important; font-weight: 600;
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

# ==========================================
# AUTO-CORRECTOR ORTOGRÁFICO (REPARA LA EXPORTACIÓN DE TU CRM)
# ==========================================
def reparar_texto_roto(texto):
    if pd.isna(texto): return ""
    t = str(texto)
    reemplazos = {
        "calibraci?n": "calibración", "Calibraci?n": "Calibración", "CALIBRACI?N": "CALIBRACIÓN",
        "medici?n": "medición", "Medici?n": "Medición", "MEDICI?N": "MEDICIÓN",
        "capacitaci?n": "capacitación", "Capacitaci?n": "Capacitación", "CAPACITACI?N": "CAPACITACIÓN",
        "M?xico": "México", "M?XICO": "MÉXICO", 
        "mec?nicos": "mecánicos", "MEC?NICOS": "MECÁNICOS",
        "ingenier?a": "ingeniería", "INGENIER?A": "INGENIERÍA",
        "tuber?as": "tuberías", "TUBER?AS": "TUBERÍAS",
        "aeron?uticas": "aeronáuticas", "AERON?UTICAS": "AERONÁUTICAS",
        "?REA": "ÁREA", "área": "área", "?rea": "área"
    }
    for mal, bien in reemplazos.items():
        t = t.replace(mal, bien)
    return t

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto", type=["csv"])

if archivo_cargado is not None:
    try:
        df_raw = pd.read_csv(archivo_cargado, encoding='latin1', on_bad_lines='skip')
    except:
        archivo_cargado.seek(0)
        df_raw = pd.read_csv(archivo_cargado, encoding='utf-8', on_bad_lines='skip')

    try:
        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        df_clean['Cotizacion'] = buscar_col(["COTIZACION"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"]).apply(reparar_texto_roto)
        df_clean['Area'] = buscar_col(["AREA", "ÁREA", "?REA"]).apply(reparar_texto_roto)
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"]).apply(reparar_texto_roto)

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
                monto_mxn_total += temp_mxn.fillna(0.0)
                monto_usd_total += temp_usd.fillna(0.0)

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total
        df = df_clean

        # FILTRO Y LIMPIEZA INICIAL
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip().str.upper()
        df = df[df['Cliente'] != 'NAN']
        df = df[df['Cliente'] != '']
        
        # ==========================================
        # REGLA MAESTRA: NORMALIZACIÓN DE RAZONES SOCIALES (FILIALES -> MATRIZ)
        # ==========================================
        def normalizar_cliente(nombre):
            n = str(nombre).upper()
            if "ITP" in n or "TUBERIAS AERONAUTICAS" in n or "TUBERÍAS AERONÁUTICAS" in n: return "ITP"
            if "TREMEC" in n or "TRANSMISIONES Y EQUIPOS" in n: return "TREMEC"
            if "CNH" in n: return "CNH"
            if "SAFRAN" in n: return "SAFRAN"
            if "BROSE" in n: return "BROSE"
            if "SIEMENS" in n: return "SIEMENS ENERGY"
            if "WATLOW" in n: return "WATLOW"
            if "STEERINGMEX" in n: return "STEERINGMEX"
            if "DANA" in n: return "DANA"
            if "BOMBARDIER" in n: return "BOMBARDIER"
            return n.strip()

        df['Cliente'] = df['Cliente'].apply(normalizar_cliente)

        # COMPLETAR DATOS VACÍOS
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

        def categorizar_unidad(area):
            area_upper = str(area).upper()
            if any(kw in area_upper for kw in ["ALTA GAMA", "EQUIPO", "CMM", "ZEISS", "SCANNER", "SCANTECH", "KREON", "BATY"]): return "ALTA GAMA"
            elif any(kw in area_upper for kw in ["LABORATORIO", "CALIBRACIÓN", "CALIBRACION", "SERVICIO", "DIMENSIONAL"]): return "LABORATORIOS"
            else: return "PRODUCTOS" 

        df['Unidad_Presupuesto'] = df['Area'].apply(categorizar_unidad)

        # FILTROS TÁCTICOS (MENÚ LATERAL)
        st.sidebar.divider()
        st.sidebar.header("Filtros Tácticos")
        
        busqueda_proyecto = st.sidebar.text_input("Buscar ID de Proyecto o Cliente:")
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]

        max_monto = float(df['Peso_Interno_Orden'].max()) if not df.empty else 1000000.0
        if pd.isna(max_monto) or max_monto == 0: max_monto = 100000.0
        
        rango_monto = st.sidebar.slider("Rango de Monto Interno", 0.0, max_monto, (0.0, max_monto), 5000.0)
        tipo_filtro_fecha = st.sidebar.selectbox("Filtrar por Fecha:", ["Sin Filtro", "Fecha de Creación", "Fecha de Cierre"])
        
        df = df[(df['Peso_Interno_Orden'] >= rango_monto[0]) & (df['Peso_Interno_Orden'] <= rango_monto[1])]

        if tipo_filtro_fecha != "Sin Filtro":
            col_fecha = 'Fecha_Creacion_DT' if tipo_filtro_fecha == "Fecha de Creación" else 'Fecha_Cierre_DT'
            min_date, max_date = df[col_fecha].min(), df[col_fecha].max()
            if pd.notna(min_date) and pd.notna(max_date):
                fecha_rango = st.sidebar.date_input("Selecciona el rango:", [min_date.date(), max_date.date()])
                if len(fecha_rango) == 2:
                    mask = (df[col_fecha].dt.date >= fecha_rango[0]) & (df[col_fecha].dt.date <= fecha_rango[1])
                    if st.sidebar.checkbox(f"Incluir registros sin {tipo_filtro_fecha}", value=True): df = df[mask | df[col_fecha].isna()]
                    else: df = df[mask]

        st.sidebar.divider()
        st.sidebar.header("Tubería Filtrada")
        st.sidebar.metric("Total USD en Proceso", f"${df['Monto_USD'].sum():,.2f}")
        st.sidebar.metric("Total MXN en Proceso", f"${df['Monto_MXN'].sum():,.2f}")

        mes_actual, anio_actual = pd.Timestamp.now().month, pd.Timestamp.now().year
        meses_es = {1:"ENERO", 2:"FEBRERO", 3:"MARZO", 4:"ABRIL", 5:"MAYO", 6:"JUNIO", 7:"JULIO", 8:"AGOSTO", 9:"SEPTIEMBRE", 10:"OCTUBRE", 11:"NOVIEMBRE", 12:"DICIEMBRE"}
        nombre_mes = meses_es.get(mes_actual, "MES ACTUAL")

        tab_finanzas, tab_ejecucion, tab_agenda = st.tabs(["Inteligencia Financiera", "Centro de Ejecución", "Agenda de Trabajo"])

        # ==========================================
        # PESTAÑA 1: FINANZAS
        # ==========================================
        with tab_finanzas:
            st.markdown("### Dashboard de Cumplimiento Mensual")
            df_mes_tracker = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)]
            
            col_b1, col_b2, col_b3 = st.columns([1.5, 1, 1])
            with col_b1:
                df_chart_usd = pd.DataFrame({
                    'Unidad': ['ALTA GAMA', 'LABORATORIOS', 'PRODUCTOS'],
                    'Radar USD': [df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_USD'].sum(),
                                  df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_USD'].sum(),
                                  df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_USD'].sum()],
                    'Meta USD': [28000.00, 15000.00, 45000.00]
                }).set_index('Unidad')
                st.markdown("#### Progreso contra Presupuesto USD")
                st.bar_chart(df_chart_usd, use_container_width=True)
                
            with col_b2:
                 st.markdown("#### Radar Capturado USD")
                 st.metric("Alta Gama (Meta: $28K)", f"${df_chart_usd.loc['ALTA GAMA', 'Radar USD']:,.0f} USD")
                 st.metric("Laboratorios (Meta: $15K)", f"${df_chart_usd.loc['LABORATORIOS', 'Radar USD']:,.0f} USD")
                 st.metric("Productos (Meta: $45K)", f"${df_chart_usd.loc['PRODUCTOS', 'Radar USD']:,.0f} USD")
                 
            with col_b3:
                 st.markdown("#### Radar Adicional MXN")
                 st.metric("Alta Gama", f"${df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_MXN'].sum():,.0f} MXN")
                 st.metric("Laboratorios", f"${df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_MXN'].sum():,.0f} MXN")
                 st.metric("Productos", f"${df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_MXN'].sum():,.0f} MXN")
            
            st.divider()
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                st.markdown("### Concentración General de Clientes")
                if not df.empty: st.bar_chart(df.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Cliente'), use_container_width=True)
            with col_f2:
                st.markdown("### Distribución General por Unidades")
                if not df.empty: st.bar_chart(df.groupby('Area')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Area'), use_container_width=True)

        # ==========================================
        # PESTAÑA 2: CENTRO DE EJECUCIÓN (TOP 10 BLINDADO)
        # ==========================================
        lista_global_seleccionados = []
        
        def render_table_interactiva(df_subset, sufijo_clave):
            if df_subset.empty: return st.info("Sin proyectos en este segmento.")
            df_mostrar = df_subset[['Cliente', 'Cotizacion', 'Descripcion', 'Monto_USD', 'Monto_MXN', 'ID_Proyecto', 'Unidad_Presupuesto']].copy()
            df_mostrar.insert(0, 'Seleccionar', False)
            df_editado = st.data_editor(
                df_mostrar, hide_index=True, use_container_width=True, key=f"tabla_{sufijo_clave}_{st.session_state.clear_key}",
                column_config={"Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False), "Cliente": st.column_config.TextColumn(disabled=True), "Cotizacion": st.column_config.TextColumn(disabled=True), "Descripcion": st.column_config.TextColumn(disabled=True), "Monto_USD": st.column_config.NumberColumn(format="$%.2f", disabled=True), "Monto_MXN": st.column_config.NumberColumn(format="$%.2f", disabled=True), "ID_Proyecto": st.column_config.TextColumn(disabled=True), "Unidad_Presupuesto": st.column_config.TextColumn(disabled=True)}
            )
            seleccion = df_editado[df_editado['Seleccionar'] == True]
            if not seleccion.empty: lista_global_seleccionados.append(seleccion)

        with tab_ejecucion:
            st.markdown("### Estructura de Cierre del Mes Corriente")
            df_mes_plan = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
            
            if not df_mes_plan.empty:
                # 1. CUENTA CLAVE GLOBAL (Sobre la data ya unificada)
                resumen_global = df.groupby('Cliente').agg({'Cotizacion': 'nunique', 'Peso_Interno_Orden': 'sum'}).reset_index().sort_values(by=['Cotizacion', 'Peso_Interno_Orden'], ascending=[False, False])
                cliente_clave = resumen_global.iloc[0]['Cliente'] if not resumen_global.empty else ""

                df_cuenta_clave = df_mes_plan[df_mes_plan['Cliente'] == cliente_clave]
                df_resto = df_mes_plan[df_mes_plan['Cliente'] != cliente_clave]
                
                st.markdown(f"#### CUENTA CLAVE (Máximo Volumen Histórico: {cliente_clave})")
                if not df_cuenta_clave.empty: render_table_interactiva(df_cuenta_clave, "cc")
                else: st.info(f"{cliente_clave} no tiene cierres programados para este mes.")
                st.divider()

                # 2. TOP 10 FIJO Y BLINDADO
                top_10_maestra = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS ENERGY", "STEERINGMEX", "TREMEC", "WATLOW"]
                top_10_filtrado = [c for c in top_10_maestra if c != cliente_clave]
                
                df_top10 = df_resto[df_resto['Cliente'].isin(top_10_filtrado)]
                df_resto_2 = df_resto[~df_resto['Cliente'].isin(top_10_filtrado)]

                # 3 y 4. 80/20 Y DESARROLLO
                if not df_resto_2.empty:
                    condicion_8020 = (df_resto_2['Monto_USD'] > 2500) | (df_resto_2['Monto_MXN'] > 50000)
                    df_8020 = df_resto_2[condicion_8020]
                    df_desarrollo = df_resto_2[~condicion_8020]
                else:
                    df_8020, df_desarrollo = pd.DataFrame(), pd.DataFrame()

                def renderizar_sub(df_datos, pre):
                    t1, t2, t3 = st.tabs(["Alta Gama", "Laboratorios", "Productos"])
                    with t1: render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'ALTA GAMA'], f"{pre}_ag")
                    with t2: render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'LABORATORIOS'], f"{pre}_lb")
                    with t3: render_table_interactiva(df_datos[df_datos['Unidad_Presupuesto'] == 'PRODUCTOS'], f"{pre}_pr")

                st.markdown("#### TOP 10 (Cuentas Estratégicas Corporativas)")
                if not df_top10.empty: renderizar_sub(df_top10, "top")
                else: st.info("Sin proyectos activos en el TOP 10 corporativo este mes.")
                
                st.markdown("#### 80/20 (Soporte Táctico)")
                if not df_8020.empty: renderizar_sub(df_8020, "8020")
                else: st.info("Sin proyectos.")
                
                st.markdown("#### DESARROLLO (Siembra a Futuro)")
                if not df_desarrollo.empty: renderizar_sub(df_desarrollo, "des")
                else: st.info("Sin proyectos.")
            else:
                st.info("No tienes cotizaciones con fecha de cierre registrada para el mes en curso.")

        # ==========================================
        # GESTIÓN RÁPIDA DE AGENDA
        # ==========================================
        with st.sidebar.container():
            st.divider()
            st.header("Programación de Ruta")
            if lista_global_seleccionados:
                df_seleccion_final = pd.concat(lista_global_seleccionados, ignore_index=True)
                st.info(f"Proyectos seleccionados: {len(df_seleccion_final)}")
                
                accion_lote = st.selectbox("Acción a ejecutar:", ["Visita Presencial", "Llamada Consultiva", "Correo y Cotización", "Cierre y Negociación"])
                fecha_lote = st.date_input("Fecha programada:", pd.Timestamp.now().date())
                
                if st.button("Agendar Seleccionados"):
                    for _, row in df_seleccion_final.iterrows():
                        nueva_tarea = pd.DataFrame([{ 'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1,10000), 'Fecha': fecha_lote, 'Cliente': row['Cliente'], 'ID_Proyecto': row['ID_Proyecto'], 'Cotizacion': row['Cotizacion'], 'Unidad_Presupuesto': row['Unidad_Presupuesto'], 'Monto_USD': row['Monto_USD'], 'Monto_MXN': row['Monto_MXN'], 'Tipo_Accion': accion_lote, 'Descripcion': row['Descripcion'], 'Completado': False }])
                        st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    st.success("Actividades agregadas.")
                    st.session_state.clear_key += 1
                    st.rerun()

        # ==========================================
        # PESTAÑA 3: AGENDA DE TRABAJO Y MINUTAS
        # ==========================================
        with tab_agenda:
            st.markdown("### Tablero de Ejecución Diaria")
            fecha_vista = st.date_input("Seleccionar día a visualizar:", pd.Timestamp.now().date())
            
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            if not df_dia.empty:
                df_dia['Peso_Temp'] = df_dia['Monto_MXN'] + (df_dia['Monto_USD'] * 19.50)
                df_dia = df_dia.sort_values(by=['Peso_Temp'], ascending=False)
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Valor USD", f"${df_dia['Monto_USD'].sum():,.0f}")
                col_m2.metric("Valor MXN", f"${df_dia['Monto_MXN'].sum():,.0f}")
                col_m3.metric("Actividades", len(df_dia))
                col_m4.metric("Visitas", len(df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]))
                
                df_mostrar = df_dia[['Completado', 'Unidad_Presupuesto', 'Tipo_Accion', 'Cliente', 'Cotizacion', 'Monto_USD', 'Monto_MXN']].copy()
                proyectos_actualizados = st.data_editor(df_mostrar, hide_index=True, use_container_width=True, key="ed_agenda")
                
                for i, idx in enumerate(df_dia.index):
                     st.session_state.agenda_radar.loc[idx, 'Completado'] = proyectos_actualizados.iloc[i]['Completado']
                     
                st.divider()
                st.markdown("### Ficha Ejecutiva y Minuta de Negociación")
                cliente_ficha = st.selectbox("Seleccionar cuenta:", df_dia['Cliente'].unique())
                
                if cliente_ficha:
                    df_cliente_sel = df_mes_plan[df_mes_plan['Cliente'] == cliente_ficha]
                    if not df_cliente_sel.empty:
                        s_usd, s_mxn = df_cliente_sel['Monto_USD'].sum(), df_cliente_sel['Monto_MXN'].sum()
                        if "Correo" in df_dia[df_dia['Cliente'] == cliente_ficha]['Tipo_Accion'].iloc[0]:
                            st.text_area("Borrador Ejecutivo:", f"Estimados señores de {cliente_ficha},\n\nNos ponemos en contacto desde MESS Servicios Metrológicos para dar seguimiento a los {len(df_cliente_sel)} requerimientos en proceso, que representan ${s_usd:,.2f} USD y ${s_mxn:,.2f} MXN.\n\nQuedamos a su disposición para coordinar la revisión detallada de estas partidas.\n\nAtentamente,\nAsesor Comercial", height=200)
                        else:
                            st.info(f"**Cuenta:** {cliente_ficha} | **Valor Mensual:** ${s_usd:,.2f} USD / ${s_mxn:,.2f} MXN")
                            for area in df_cliente_sel['Unidad_Presupuesto'].unique():
                                st.markdown(f"##### 📌 {area}")
                                for _, r in df_cliente_sel[df_cliente_sel['Unidad_Presupuesto'] == area].iterrows():
                                    st.markdown(f"> **Folio {r['Cotizacion']}** (Ref. {r['ID_Proyecto']}): {str(r['Descripcion']).capitalize()} — **Monto:** ${r['Monto_USD']:,.2f} USD / ${r['Monto_MXN']:,.2f} MXN")
                    else: st.warning("Sin datos de cierre para esta cuenta este mes.")

                if st.button("Limpiar actividades finalizadas"):
                    st.session_state.agenda_radar = st.session_state.agenda_radar[~((st.session_state.agenda_radar['Fecha'] == fecha_vista) & (st.session_state.agenda_radar['Completado'] == True))]
                    st.rerun()
            else:
                st.info("Agenda libre.")

    except Exception as e:
        st.error(f"Error de sistema. Detalles: {e}")
