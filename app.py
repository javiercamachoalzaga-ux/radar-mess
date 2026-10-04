import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import google.generativeai as genai
import urllib.parse
import io
import json
import sqlite3

# Intenta importar la librería de Word
try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# CONFIGURACIÓN GEMINI API
# ==========================================
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS SQLITE (REVOPS)
# ==========================================
def init_db():
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    # Tabla Agenda
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, cliente TEXT, contacto TEXT,
            objetivo TEXT, estatus TEXT
        )
    """)
    
    # Migración Agenda (Horario)
    cursor.execute("PRAGMA table_info(agenda)")
    columnas_agenda = [col[1] for col in cursor.fetchall()]
    if 'horario' not in columnas_agenda:
        cursor.execute("ALTER TABLE agenda ADD COLUMN horario TEXT DEFAULT '09:00'")
        
    # Tabla Reportes (Bitácora Post-Visita)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_rep TEXT, cliente TEXT, resumen TEXT,
            pain TEXT, monto REAL, probabilidad INTEGER,
            semana TEXT, siguiente_paso TEXT, proxima_fecha TEXT,
            estatus TEXT
        )
    """)
    
    # Migración Reportes (Moneda)
    cursor.execute("PRAGMA table_info(reportes)")
    columnas_reportes = [col[1] for col in cursor.fetchall()]
    if 'moneda' not in columnas_reportes:
        cursor.execute("ALTER TABLE reportes ADD COLUMN moneda TEXT DEFAULT 'MXN'")
        
    conn.commit()
    conn.close()

init_db()

def run_query(query, params=(), fetch=True):
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    if fetch:
        data = cursor.fetchall()
        conn.close()
        return data
    conn.commit()
    conn.close()

# ==========================================
# MEMORIA DE SESIÓN (STATE)
# ==========================================
if 'proyecto_foco' not in st.session_state: st.session_state.proyecto_foco = None
if 'tactica_analisis' not in st.session_state: st.session_state.tactica_analisis = ""
if 'tactica_mensaje' not in st.session_state: st.session_state.tactica_mensaje = ""
if 'tactica_objeciones' not in st.session_state: st.session_state.tactica_objeciones = ""
if 'tactica_marketing' not in st.session_state: st.session_state.tactica_marketing = ""
if 'tactica_bitacora' not in st.session_state: st.session_state.tactica_bitacora = ""
if 'tactica_cliente' not in st.session_state: st.session_state.tactica_cliente = ""
if 'tactica_id' not in st.session_state: st.session_state.tactica_id = ""
if 'tactica_equipo' not in st.session_state: st.session_state.tactica_equipo = ""
if 'tactica_monto' not in st.session_state: st.session_state.tactica_monto = ""

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo-radar { font-size: 38px; font-weight: 900; color: #003a70; margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #555555; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #7f8c8d !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important; }
    .stDataFrame { font-size: 14px !important; }
    .ficha-scott { background-color: #f4f6f7; padding: 20px; border-radius: 8px; border: 1px solid #d5d8dc; margin-bottom: 20px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

def check_password():
    if "mi_contrasena" not in st.secrets: return True
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña", type="password")
    if pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral para acceder al sistema.")
    st.stop()

st.markdown('<div class="titulo-radar">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Módulo CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)

# ==========================================
# TABS DE NAVEGACIÓN
# ==========================================
tab_dashboards, tab_enablement, tab_scott, tab_revops = st.tabs([
    "1. Dashboards CRM", 
    "2. Proyectos Estancados", 
    "3. Laboratorio IA (Estrategia Integral)",
    "4. Gestión Comercial (RevOps)"
])

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])

if archivo_cargado is not None:
    try:
        # --- LECTOR ROBUSTO SCOTT ---
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1', header=None, sep=None, engine='python')
        header_idx = -1
        
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.dropna()]).strip()
            if 'PROYECTO' in row_str and 'CLIENTE' in row_str:
                header_idx = idx
                break
                
        if header_idx == -1:
            st.error("No se detectó el formato del CRM. Asegúrate de subir la plantilla original de SCOTT.")
            st.stop()
            
        headers = [str(x).upper().replace('\ufeff', '').strip() for x in df_raw.iloc[header_idx] if pd.notna(x)]
        df_data = df_raw.iloc[header_idx+1:].copy()
        df_data = df_data.dropna(axis=1, how='all')
        
        if len(df_data.columns) >= len(headers):
            df_data = df_data.iloc[:, :len(headers)]
            df_data.columns = headers
        else:
            df_data.columns = headers[:len(df_data.columns)]

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_data.columns:
                    col_limpia = str(col).upper().strip()
                    if col_limpia == clave or col_limpia == f"{clave}.1":
                        return df_data[col].copy()
            return pd.Series([None] * len(df_data))

        # --- CONSTRUCCIÓN INICIAL (SIN BORRAR FILAS AÚN) ---
        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO", "FOLIO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "EMPRESA"])
        df_clean['Cotizacion'] = buscar_col(["COTIZACION", "COTIZACIÓN"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def extraer_numero(val_str):
            try:
                v = str(val_str).upper().replace('$', '').replace('USD', '').replace('MXN', '').replace(' ', '').strip()
                if ',' in v and '.' in v:
                    v = v.replace(',', '')
                elif ',' in v and len(v.split(',')[-1]) != 2:
                    v = v.replace(',', '')
                elif ',' in v and len(v.split(',')[-1]) == 2:
                    v = v.replace(',', '.')
                v = ''.join(c for c in v if c.isdigit() or c == '.')
                return float(v) if v else 0.0
            except: 
                return 0.0

        # --- MOTOR EXTRACCIÓN DE MONEDAS ---
        monto_mxn = np.zeros(len(df_data))
        monto_usd = np.zeros(len(df_data))
        col_moneda = buscar_col(["MONEDA", "DIVISA"])
        
        for col in df_data.columns:
            col_name = str(col).upper().strip()
            if any(k in col_name for k in ["VALOR", "MONTO", "IMPORTE", "TOTAL"]):
                is_col_usd = 'USD' in col_name or 'US$' in col_name
                
                for i in range(len(df_data)):
                    val_raw = df_data[col].iloc[i]
                    val_str = str(val_raw).upper()
                    num = extraer_numero(val_raw)
                    
                    moneda_fila = str(col_moneda.iloc[i]).upper() if not col_moneda.isna().all() else ""
                    
                    if is_col_usd or 'USD' in val_str or 'US$' in val_str or 'USD' in moneda_fila or 'US$' in moneda_fila or 'DÓLA' in moneda_fila or 'DOLA' in moneda_fila:
                        monto_usd[i] += num
                    else:
                        monto_mxn[i] += num
                        
        df_clean['Monto_MXN'] = monto_mxn
        df_clean['Monto_USD'] = monto_usd

        # --- AHORA SÍ, FILTRAMOS LAS FILAS VACÍAS ---
        df_clean = df_clean.dropna(subset=['ID_Proyecto']).reset_index(drop=True)

        def sanear_y_limpiar(texto):
            if pd.isna(texto): return ""
            return re.sub(r'\s+', ' ', str(texto).replace("?", "ó")).strip().title()

        for col in ['Cliente', 'Descripcion', 'Area', 'Estatus', 'Etapa']:
            df_clean[col] = df_clean[col].apply(sanear_y_limpiar)

        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        # AGRUPACIÓN POR PROYECTO
        df = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first',
            'Cotizacion': lambda x: ' / '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Area': 'first', 'Fecha_Creacion': 'first', 'Fecha_Cierre': 'first',
            'Estatus': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum', 'Monto_USD': 'sum'
        }).reset_index()

        df.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        # Filtramos para mostrar solo proyectos con valor monetario
        df = df[(df['Monto_MXN'] > 0) | (df['Monto_USD'] > 0)]
        
        filtro_estatus = df['Estatus'].str.contains('PROCESO', case=False, na=False)
        filtro_etapa = df['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)
        df = df[filtro_estatus | filtro_etapa].copy()
        
        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama"
            elif any(k in texto for k in ["CALIBRACIÓN", "LABORATORIO", "DIMENSIONAL"]): return "2. Calibraciones"
            else: return "3. Productos Generales"
        
        df['Pilar_Estrategico'] = df.apply(clasificar_pilar, axis=1)
        
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            else: return "5. En Proceso"
            
        df['Fase_Pipeline'] = df['Etapa'].apply(clasificar_fase)
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)
        df['Días_Activo'] = (pd.Timestamp.now() - df['Fecha_Creacion_DT']).dt.days

        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        opciones_pilares = df['Pilar_Estrategico'].unique().tolist()
        filtro_pilar = st.sidebar.multiselect("Filtrar por Pilar:", opciones_pilares, default=opciones_pilares)
        busqueda_proyecto = st.sidebar.text_input("Buscar Folio o Cliente:")
        
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]
        if filtro_pilar:
            df = df[df['Pilar_Estrategico'].isin(filtro_pilar)]

        # ==========================================
        # TAB 1: DASHBOARDS CRM
        # ==========================================
        with tab_dashboards:
            st.markdown("### Análisis de Forecast vs Cuota ($80K USD)")
            META_MENSUAL_USD = 80000.00
            
            usd_caliente = df[df['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_USD'].sum()
            mxn_caliente = df[df['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_MXN'].sum()
            
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("Meta Comercial Mensual", f"${META_MENSUAL_USD:,.2f} USD")
            col_g2.metric("Pipeline Probable (Activo)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN extra")
            if (META_MENSUAL_USD - usd_caliente) > 0:
                col_g3.metric("GAP (Brecha para Meta)", f"${(META_MENSUAL_USD - usd_caliente):,.2f} USD", "- Acción requerida")
            else:
                col_g3.metric("GAP (Brecha)", "$0.00 USD", "+ Meta Cubierta")
            
            st.divider()
            col_sel1, col_sel2 = st.columns([1, 3])
            with col_sel1: moneda_sel = st.selectbox("Seleccionar Moneda para Gráficos:", ["USD ($)", "MXN ($)"])
            col_val = 'Monto_USD' if moneda_sel == "USD ($)" else 'Monto_MXN'
            
            st.divider()
            
            if not df.empty:
                st.markdown(f"#### Análisis Pareto 80/20 por Cuentas Clave ({moneda_sel})")
                df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
                df_pareto = df_pareto[df_pareto[col_val] > 0].sort_values(by=col_val, ascending=False).reset_index(drop=True)
                if not df_pareto.empty:
                    df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
                    df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
                    
                    barras_pareto = alt.Chart(df_pareto).mark_bar(color='#34495e').encode(
                        x=alt.X('Cliente', sort=None, title='Cliente', axis=alt.Axis(labelLimit=0)),
                        y=alt.Y(col_val, title=f'Valor'),
                        tooltip=['Cliente', alt.Tooltip(col_val, format='$,.2f'), alt.Tooltip('Porcentaje', format='.1%')]
                    )
                    linea_pareto = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(
                        x=alt.X('Cliente', sort=None),
                        y=alt.Y('Acumulado', title='Porcentaje Acumulado', axis=alt.Axis(format='%')),
                        tooltip=['Cliente', alt.Tooltip('Acumulado', format='.1%')]
                    )
                    st.altair_chart(alt.layer(barras_pareto, linea_pareto).resolve_scale(y='independent').properties(height=450), use_container_width=True)
                
                st.divider()
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown(f"**Forecast por Área**")
                    df_areas = df.groupby('Area')[col_val].sum().reset_index()
                    if not df_areas.empty: st.altair_chart(alt.Chart(df_areas[df_areas[col_val]>0]).mark_bar(color='#003a70').encode(x=alt.X(col_val, title=''), y=alt.Y('Area', sort='-x', title=''), tooltip=['Area', alt.Tooltip(col_val, format='$,.2f')]).properties(height=350), use_container_width=True)
                with col_g2:
                    st.markdown(f"**Salud del Embudo**")
                    df_graf_fases = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
                    if not df_graf_fases.empty: st.altair_chart(alt.Chart(df_graf_fases[df_graf_fases[col_val]>0]).mark_bar(color='#2ecc71').encode(x=alt.X(col_val, title=''), y=alt.Y('Fase_Pipeline', sort='-x', title=''), tooltip=['Fase_Pipeline', alt.Tooltip(col_val, format='$,.2f')]).properties(height=350), use_container_width=True)

        # ==========================================
        # TAB 2: ENABLEMENT
        # ==========================================
        with tab_enablement:
            st.markdown("### Riesgo Operativo y Proyectos Estancados")
            estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Monto_USD', ascending=False)
            if not estancados.empty:
                for _, row in estancados.head(4).iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['ID_Proyecto']} | {row['Cliente']}**")
                        st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Riesgo: **${row['Monto_USD']:,.2f} USD**")
            else:
                st.success("Embudo limpio.")
                
            st.divider()
            st.markdown("#### Auditoría Rápida CRM")
            st.dataframe(df[['ID_Proyecto', 'Cliente', 'Descripcion', 'Fase_Pipeline', 'Monto_USD', 'Monto_MXN']], use_container_width=True, hide_index=True)

        # ==========================================
        # TAB 3: LABORATORIO TÁCTICO IA
        # ==========================================
        with tab_scott:
            st.markdown("### Copiloto Estratégico (Key Account Management)")
            st.caption("Arma estrategias para un proyecto único o consolida varios proyectos en una sola negociación de paquete.")
            
            clientes_disponibles = sorted(df['Cliente'].unique().tolist())
            cliente_seleccionado = st.selectbox("1. Selecciona la Cuenta / Cliente:", ["-- Selecciona un cliente --"] + clientes_disponibles)
            
            if cliente_seleccionado != "-- Selecciona un cliente --":
                df_cliente = df[df['Cliente'] == cliente_seleccionado]
                
                opciones_proyectos_cliente = df_cliente.apply(lambda x: f"[{x['ID_Proyecto']}] {str(x['Descripcion'])} - ${x['Monto_USD']:,.0f} USD / ${x['Monto_MXN']:,.0f} MXN", axis=1).tolist()
                proyectos_seleccionados = st.multiselect("2. Selecciona los folios a incluir en esta estrategia:", opciones_proyectos_cliente)
                
                if proyectos_seleccionados:
                    ids_seleccionados = [opc.split("]")[0].replace("[", "") for opc in proyectos_seleccionados]
                    df_seleccion = df[df['ID_Proyecto'].astype(str).isin(ids_seleccionados)]
                    
                    monto_total_usd = df_seleccion['Monto_USD'].sum()
                    monto_total_mxn = df_seleccion['Monto_MXN'].sum()
                    equipos_combinados = " | ".join(df_seleccion['Descripcion'].tolist())
                    ids_combinados = ", ".join(df_seleccion['ID_Proyecto'].astype(str).tolist())
                    es_paquete = len(df_seleccion) > 1
                    
                    st.markdown(f"""
                    <div class="ficha-scott">
                        <h4>{cliente_seleccionado} (Folios: {ids_combinados})</h4>
                        <b>Equipos Involucrados:</b> <span style='color:#003a70;'>{equipos_combinados}</span><br>
                        <b>Monto Total a Negociar:</b> <span style='color:#27ae60; font-weight:bold; font-size:18px;'>${monto_total_usd:,.2f} USD</span> | <span style='color:#8e44ad; font-weight:bold;'>${monto_total_mxn:,.2f} MXN</span>
                        {'<br><span style="color:#e67e22; font-weight:bold;">⚠️ Estrategia de Paquete (Bundle) Activada</span>' if es_paquete else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("#### Configuración de la Táctica")
                    tipo_operacion = st.radio("Objetivo Principal:", ["Aceleración y Cierre (Virtual)", "Apertura y Visitas (Presencial)"], horizontal=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        if tipo_operacion == "Aceleración y Cierre (Virtual)":
                            sub_opcion = st.radio("¿Qué canal vas a usar?", ["Mensaje de WhatsApp", "Correo Electrónico Ejecutivo", "Guion de Llamada Telefónica"])
                        else:
                            sub_opcion = st.radio("¿Qué tipo de visita harás?", [
                                "Visita de Prospección (Primer Contacto)",
                                "Visita Técnica (Acompañado de Product Manager)",
                                "Visita Estratégica / Negociación (Con Gerencia o Dirección)"
                            ])
                        interlocutor = st.selectbox("Perfil del Interlocutor:", ["Ingeniero / Calidad / Mantenimiento", "Comprador / Finanzas / Gerente Planta", "Director / Dueño"])
                    
                    with col2: 
                        giro_cliente = st.text_input("Giro o Terminología del cliente (Ej. 'Usar casting, no fundición. Sector Aeroespacial'):", placeholder="Sector, términos clave a usar o evitar...")
                        contexto_manual = st.text_area("Notas de situación actual (Ej. 'Están evaluando a Zeiss, no tienen presupuesto liberado'):", height=100)
                    
                    if gemini_activo:
                        if st.button("🧠 Generar Estrategia Consultiva", type="primary", use_container_width=True):
                            with st.spinner("Diseñando estrategia empática y consolidando información en formato estricto..."):
                                try:
                                    safety_settings = [
                                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                                    ]

                                    model = genai.GenerativeModel("gemini-3.6-flash", generation_config={"temperature": 0.4, "max_output_tokens": 2500, "top_p": 0.8})

                                    prompt_maestro = f"""
                                    Eres Javier Camacho, un Asesor Consultivo B2B y Key Account Manager de MESS Servicios Metrológicos.
                                    
                                    CONTEXTO DE LA NEGOCIACIÓN:
                                    Cliente: {cliente_seleccionado} (Perfil: {interlocutor})
                                    Giro e Instrucciones de Terminología: {giro_cliente}
                                    Equipos/Servicios: {equipos_combinados}
                                    Monto Total: ${monto_total_usd} USD y ${monto_total_mxn} MXN
                                    Proyectos Agrupados: {len(df_seleccion)}
                                    Acción Solicitada: {sub_opcion}
                                    Notas Adicionales: {contexto_manual}
                                    
                                    DIRECTRICES DE TONO (MANDATORIO POR DIRECCIÓN GENERAL):
                                    - COMUNICACIÓN HUMANIZADA: Escribe de humano a humano. Sé profesional, empático, natural y conversacional.
                                    - CERO EXAGERACIÓN TÉCNICA: No uses términos rimbombantes. Menciona la técnica de forma sutil solo si el cliente la requiere para entender el valor.
                                    - ADAPTACIÓN AL GIRO: Respeta estrictamente el giro y la terminología indicada. No inventes procesos industriales que no aplican.
                                    - SI HAY MÚLTIPLES PROYECTOS: Tu estrategia DEBE enfocarse en vender esto como un "Paquete" o "Solución Integral" (Bundle) para facilitar la decisión del cliente y negociar mejores condiciones globales.
                                    
                                    INTEGRACIÓN METODOLÓGICA INVISIBLE:
                                    Usa MEDDPICC para mapear la cuenta, SPIN para tocar el dolor, y Sandler para el cierre (buscar el sí/no claro sin rogar). Aplícalo en el análisis y en los mensajes de forma invisible y fluida.
                                    
                                    FORMATO DE SALIDA ESTRICTO (ETIQUETAS XML OBLIGATORIAS):
                                    Debes estructurar tu respuesta utilizando ÚNICAMENTE las siguientes etiquetas XML en inglés. El texto adentro de las etiquetas debe ser en ESPAÑOL. NO uses formato JSON. Usa este formato exacto:

                                    <ANALYSIS>
                                    (Análisis estratégico humano. Evalúa la cuenta y explica cómo vender la solución (o el paquete si son varios). Define cómo usar Sandler aquí.)
                                    </ANALYSIS>

                                    <MESSAGE>
                                    (Redacta el texto exacto para el canal seleccionado: {sub_opcion}. Muy humano, claro, empático y al punto.)
                                    </MESSAGE>

                                    <OBJECTIONS>
                                    (Menciona 2 posibles objeciones del cliente ante esta propuesta y cómo rebatirlas como consultor experto, no como folleto.)
                                    </OBJECTIONS>

                                    <MARKETING>
                                    (Instrucción para el equipo de Marketing sobre qué material de apoyo enviar para esta cuenta/giro)
                                    </MARKETING>

                                    <LOG>
                                    (Reporte súper breve para pegar en el CRM SCOTT)
                                    </LOG>
                                    """
                                    
                                    response = model.generate_content(prompt_maestro, safety_settings=safety_settings)
                                    texto_raw = response.text
                                    
                                    def extract_xml(tag, text):
                                        match = re.search(fr'<{tag}[^>]*>(.*?)</{tag}>', text, re.DOTALL | re.IGNORECASE)
                                        return match.group(1).strip() if match else "Error aislando sección."

                                    st.session_state.tactica_analisis = extract_xml('ANALYSIS', texto_raw)
                                    st.session_state.tactica_mensaje = extract_xml('MESSAGE', texto_raw)
                                    st.session_state.tactica_objeciones = extract_xml('OBJECTIONS', texto_raw)
                                    st.session_state.tactica_marketing = extract_xml('MARKETING', texto_raw)
                                    st.session_state.tactica_bitacora = extract_xml('LOG', texto_raw)
                                    
                                    if "Error aislando" in st.session_state.tactica_mensaje:
                                        st.session_state.tactica_mensaje = texto_raw
                                    
                                    st.session_state.tactica_cliente = cliente_seleccionado
                                    st.session_state.tactica_id = ids_combinados
                                    st.session_state.tactica_equipo = equipos_combinados
                                    st.session_state.tactica_monto = f"${monto_total_usd:,.2f} USD / ${monto_total_mxn:,.2f} MXN"
                                    
                                except Exception as e:
                                    st.error(f"Error de IA: {e}")

                    # VISTA DE RESULTADOS
                    if st.session_state.tactica_mensaje:
                        st.success(f"Estrategia Consultiva generada con éxito para: {sub_opcion}")
                        
                        st.markdown("#### 🧠 Análisis Estratégico (KAM / Empaquetado)")
                        st.info(st.session_state.tactica_analisis)
                        
                        st.markdown(f"#### 💬 Acción Ejecutada: {sub_opcion}")
                        st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_mensaje}</div>", unsafe_allow_html=True)
                        
                        st.markdown("#### 🛡️ Manejo de Objeciones")
                        st.warning(st.session_state.tactica_objeciones)
                        
                        st.markdown("#### 🎯 Solicitud Marketing (ABM)")
                        st.info(st.session_state.tactica_marketing)
                        
                        st.markdown("#### 📋 Bitácora CRM (SCOTT)")
                        st.success(st.session_state.tactica_bitacora)
                            
                        if docx_disponible:
                            st.divider()
                            st.markdown("### 📤 Exportar Documento")
                            def exportar_todo():
                                doc = Document()
                                doc.add_heading("ESTRATEGIA KAM | REVENUE OPERATIONS", 0)
                                doc.add_paragraph(f"Cliente: {st.session_state.tactica_cliente}\nFolios Agrupados: {st.session_state.tactica_id}\nEquipos/Servicios: {st.session_state.tactica_equipo}\nValor Total: {st.session_state.tactica_monto}")
                                doc.add_heading("1. Análisis Estratégico", 1)
                                doc.add_paragraph(st.session_state.tactica_analisis)
                                doc.add_heading(f"2. Acción: {sub_opcion}", 1)
                                doc.add_paragraph(st.session_state.tactica_mensaje)
                                doc.add_heading("3. Manejo de Objeciones", 1)
                                doc.add_paragraph(st.session_state.tactica_objeciones)
                                doc.add_heading("4. Marketing ABM", 1)
                                doc.add_paragraph(st.session_state.tactica_marketing)
                                doc.add_heading("5. Registro CRM", 1)
                                doc.add_paragraph(st.session_state.tactica_bitacora)
                                buffer = io.BytesIO()
                                doc.save(buffer)
                                buffer.seek(0)
                                return buffer

                            st.download_button("💾 Descargar Estrategia Completa (.docx)", data=exportar_todo(), file_name=f"EstrategiaKAM_{st.session_state.tactica_cliente.replace(' ','_')}.docx", use_container_width=True)
    except Exception as e:
        st.error(f"Error procesando CSV: {e}")
else:
    with tab_dashboards: st.warning("Sube el archivo CSV del CRM SCOTT en la barra lateral para ver tus datos.")
    with tab_enablement: st.warning("Requiere datos.")
    with tab_scott: st.warning("Requiere datos.")

# ==========================================
# NUEVA ESTACIÓN 4: GESTIÓN COMERCIAL (REVOPS) 
# Esta sección es independiente de la carga del CSV
# ==========================================
with tab_revops:
    st.markdown("### 🚀 Revenue Operations & Ejecución Comercial")

    t_agenda, t_bitacora, t_forecast, t_reportes = st.tabs([
        "📅 Agenda de Visitas",
        "📝 Bitácora Post-Visita",
        "📈 Forecast Semanal",
        "📄 Generador de Reportes"
    ])

    # --- SUBMÓDULO 1: AGENDA ---
    with t_agenda:
        st.subheader("Programación y Control de Visitas")
        with st.form("form_agenda", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_fecha = st.date_input("Fecha de Visita")
                f_horario = st.time_input("Horario", value=datetime.strptime('09:00', '%H:%M').time())
                f_cliente = st.text_input("Empresa / Cliente")
            with c2:
                f_contacto = st.text_input("Contacto Clave")
                f_estatus = st.selectbox("Estatus", ["Programada", "Confirmada", "Realizada", "Reprogramada"])
            with c3:
                f_objetivo = st.text_area("Objetivo", placeholder="Ej. Presentación...")
            
            if st.form_submit_button("💾 Guardar en Agenda"):
                if f_cliente:
                    run_query("INSERT INTO agenda (fecha, horario, cliente, contacto, objetivo, estatus) VALUES (?, ?, ?, ?, ?, ?)",
                              (str(f_fecha), str(f_horario.strftime('%H:%M')), f_cliente, f_contacto, f_objetivo, f_estatus), fetch=False)
                    st.success(f"Visita con {f_cliente} agendada.")
                    st.rerun()
                else:
                    st.error("Ingresa el cliente.")

        st.markdown("#### 📋 Visitas Registradas")
        visitas = run_query("SELECT id, fecha, horario, cliente, contacto, objetivo, estatus FROM agenda ORDER BY fecha DESC, horario DESC")
        if visitas:
            st.dataframe(pd.DataFrame(visitas, columns=["ID", "Fecha", "Horario", "Cliente", "Contacto", "Objetivo", "Estatus"]), use_container_width=True, hide_index=True)
            
            # --- PANEL DE EDICIÓN / ELIMINACIÓN (AGENDA) ---
            with st.expander("✏️ Editar o Eliminar Visita Registrada"):
                opc_visitas = {f"ID {v[0]} - {v[3]} ({v[1]} a las {v[2]})": v for v in visitas}
                sel_v = st.selectbox("Selecciona el registro a modificar:", list(opc_visitas.keys()))
                v_data = opc_visitas[sel_v]
                
                ce1, ce2, ce3 = st.columns(3)
                with ce1:
                    e_fecha = st.text_input("Fecha", value=v_data[1])
                    e_horario = st.text_input("Horario (HH:MM)", value=v_data[2])
                    e_cliente = st.text_input("Cliente", value=v_data[3])
                with ce2:
                    e_contacto = st.text_input("Contacto", value=v_data[4])
                    idx_estatus = ["Programada", "Confirmada", "Realizada", "Reprogramada"].index(v_data[6]) if v_data[6] in ["Programada", "Confirmada", "Realizada", "Reprogramada"] else 0
                    e_estatus = st.selectbox("Actualizar Estatus", ["Programada", "Confirmada", "Realizada", "Reprogramada"], index=idx_estatus)
                with ce3:
                    e_objetivo = st.text_area("Objetivo", value=v_data[5])
                
                b_edit, b_del = st.columns(2)
                with b_edit:
                    if st.button("🔄 Actualizar Visita", type="primary"):
                        run_query("UPDATE agenda SET fecha=?, horario=?, cliente=?, contacto=?, objetivo=?, estatus=? WHERE id=?", 
                                  (e_fecha, e_horario, e_cliente, e_contacto, e_objetivo, e_estatus, v_data[0]), fetch=False)
                        st.success("Cita actualizada exitosamente.")
                        st.rerun()
                with b_del:
                    if st.button("🗑️ Eliminar Visita"):
                        run_query("DELETE FROM agenda WHERE id=?", (v_data[0],), fetch=False)
                        st.warning("Cita eliminada de la base de datos.")
                        st.rerun()
        else:
            st.info("Sin visitas agendadas.")

    # --- SUBMÓDULO 2: BITÁCORA ---
    with t_bitacora:
        st.subheader("Bitácora Comercial Post-Visita")
        with st.form("form_reporte", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                r_fecha = st.date_input("Fecha del Reporte")
                r_cliente = st.text_input("Cliente Visitado")
                r_semana = st.selectbox("Semana Comercial", ["W1", "W2", "W3", "W4"])
            with c2:
                r_moneda = st.selectbox("Moneda", ["MXN", "USD"])
                r_monto = st.number_input("Monto Estimado", min_value=0.0, step=1000.0, format="%.2f")
                r_prob = st.slider("Probabilidad de Cierre (%)", 0, 100, 50, 5)
            with c3:
                r_estatus = st.selectbox("Estatus de Oportunidad", ["Prospecto", "Cotizado", "Negociación", "Cerrado Ganado"])
                r_pain = st.text_input("Dolores (Pain)", placeholder="Ej. Paros de máquina...")
                r_paso = st.text_input("Siguiente Paso")
                r_prox_fecha = st.date_input("Próxima Fecha")
            
            if st.form_submit_button("💾 Guardar Reporte"):
                if r_cliente:
                    run_query("INSERT INTO reportes (fecha_rep, cliente, resumen, pain, monto, probabilidad, semana, siguiente_paso, proxima_fecha, estatus, moneda) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (str(r_fecha), r_cliente, "Seguimiento", r_pain, r_monto, r_prob, r_semana, r_paso, str(r_prox_fecha), r_estatus, r_moneda), fetch=False)
                    st.success("Bitácora guardada.")
                    st.rerun()
                else:
                    st.error("Ingresa el cliente.")

        st.markdown("#### 🗂️ Historial")
        reportes_db = run_query("SELECT id, cliente, monto, probabilidad, semana, estatus, proxima_fecha, fecha_rep, pain, siguiente_paso, moneda FROM reportes ORDER BY fecha_rep DESC")
        if reportes_db:
            df_rep = pd.DataFrame(reportes_db, columns=["ID", "Cliente", "Monto", "Prob(%)", "Semana", "Estatus", "Siguiente", "Fecha Rep", "Pain", "Siguiente Paso", "Moneda"])
            # Formatear la columna de monto para que se vea limpio con su divisa
            df_rep["Monto"] = df_rep.apply(lambda x: f"${x['Monto']:,.2f} {x['Moneda']}", axis=1)
            # Quitar columnas extra para la vista rápida
            st.dataframe(df_rep.drop(columns=["Fecha Rep", "Pain", "Siguiente Paso", "Moneda"]), use_container_width=True, hide_index=True)
            
            # --- PANEL DE EDICIÓN / ELIMINACIÓN (BITÁCORA) ---
            with st.expander("✏️ Editar o Eliminar Reporte Guardado"):
                opc_reps = {f"ID {r[0]} - {r[1]} (${r[2]} {r[10]})": r for r in reportes_db}
                sel_r = st.selectbox("Selecciona el reporte a modificar:", list(opc_reps.keys()))
                r_data = opc_reps[sel_r]
                
                re1, re2, re3 = st.columns(3)
                with re1:
                    er_fecha = st.text_input("Fecha Reporte", value=r_data[7])
                    er_cliente = st.text_input("Empresa", value=r_data[1])
                    idx_sem = ["W1", "W2", "W3", "W4"].index(r_data[4]) if r_data[4] in ["W1", "W2", "W3", "W4"] else 0
                    er_semana = st.selectbox("Semana", ["W1", "W2", "W3", "W4"], index=idx_sem)
                with re2:
                    idx_moneda = ["MXN", "USD"].index(r_data[10]) if r_data[10] in ["MXN", "USD"] else 0
                    er_moneda = st.selectbox("Moneda", ["MXN", "USD"], index=idx_moneda)
                    er_monto = st.number_input("Monto", value=float(r_data[2]), step=1000.0)
                    er_prob = st.slider("Probabilidad (%)", 0, 100, int(r_data[3]))
                with re3:
                    idx_est = ["Prospecto", "Cotizado", "Negociación", "Cerrado Ganado"].index(r_data[5]) if r_data[5] in ["Prospecto", "Cotizado", "Negociación", "Cerrado Ganado"] else 0
                    er_estatus = st.selectbox("Estatus Comercial", ["Prospecto", "Cotizado", "Negociación", "Cerrado Ganado"], index=idx_est)
                    er_pain = st.text_area("Pain / Dolores", value=r_data[8])
                    er_paso = st.text_input("Siguiente Acción", value=r_data[9])
                    er_prox = st.text_input("Fecha Prox. Acción", value=r_data[6])
                
                br_edit, br_del = st.columns(2)
                with br_edit:
                    if st.button("🔄 Actualizar Reporte", type="primary"):
                        run_query("UPDATE reportes SET fecha_rep=?, cliente=?, semana=?, monto=?, probabilidad=?, estatus=?, pain=?, siguiente_paso=?, proxima_fecha=?, moneda=? WHERE id=?", 
                                  (er_fecha, er_cliente, er_semana, er_monto, er_prob, er_estatus, er_pain, er_paso, er_prox, er_moneda, r_data[0]), fetch=False)
                        st.success("Reporte actualizado correctamente.")
                        st.rerun()
                with br_del:
                    if st.button("🗑️ Eliminar Reporte"):
                        run_query("DELETE FROM reportes WHERE id=?", (r_data[0],), fetch=False)
                        st.warning("Reporte eliminado definitivamente.")
                        st.rerun()
        else:
            st.info("No hay reportes registrados.")

    # --- SUBMÓDULO 3: FORECAST ---
    with t_forecast:
        st.subheader("Panel de Forecast (Pipeline Ponderado)")
        data_fc = run_query("SELECT monto, probabilidad, semana, moneda FROM reportes")
        if data_fc:
            df_fc = pd.DataFrame(data_fc, columns=["Monto", "Prob", "Semana", "Moneda"])
            df_fc["Forecast"] = df_fc["Monto"] * (df_fc["Prob"] / 100.0)
            
            mxn_pipe = df_fc[df_fc["Moneda"] == "MXN"]["Monto"].sum()
            mxn_fc = df_fc[df_fc["Moneda"] == "MXN"]["Forecast"].sum()
            
            usd_pipe = df_fc[df_fc["Moneda"] == "USD"]["Monto"].sum()
            usd_fc = df_fc[df_fc["Moneda"] == "USD"]["Forecast"].sum()
            
            st.markdown("##### Vista Financiera Global")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pipeline (MXN)", f"${mxn_pipe:,.2f}")
            c2.metric("Forecast Real (MXN)", f"${mxn_fc:,.2f}")
            c3.metric("Pipeline (USD)", f"${usd_pipe:,.2f}")
            c4.metric("Forecast Real (USD)", f"${usd_fc:,.2f}")
            
            st.markdown("#### Desglose por Semana y Moneda")
            df_group = df_fc.groupby(["Semana", "Moneda"]).agg(Pipeline_Total=("Monto", "sum"), Forecast=("Forecast", "sum"), Oportunidades=("Monto", "count")).reset_index()
            # Formatear el DataFrame visualmente
            df_group["Pipeline_Total"] = df_group.apply(lambda x: f"${x['Pipeline_Total']:,.2f}", axis=1)
            df_group["Forecast"] = df_group.apply(lambda x: f"${x['Forecast']:,.2f}", axis=1)
            st.dataframe(df_group, use_container_width=True, hide_index=True)
        else:
            st.info("Agrega reportes para visualizar el forecast.")

    # --- SUBMÓDULO 4: REPORTES ---
    with t_reportes:
        st.subheader("Generador de Reportes (Correo/Word)")
        clientes_list = run_query("SELECT DISTINCT cliente FROM reportes")
        if clientes_list:
            cliente_sel = st.selectbox("Selecciona Cliente", [c[0] for c in clientes_list])
            if cliente_sel:
                d = run_query("SELECT fecha_rep, pain, monto, probabilidad, semana, siguiente_paso, proxima_fecha, estatus, moneda FROM reportes WHERE cliente = ? ORDER BY id DESC LIMIT 1", (cliente_sel,))[0]
                
                correo = f"Estimado equipo,\n\nVisita de seguimiento técnico-comercial el {d[0]} ({d[4]}).\n- Pain: {d[1]}\n- Monto: ${d[2]:,.2f} {d[8]} ({d[3]}% prob)\n- Estatus: {d[7]}\n- Siguiente Paso: {d[5]} ({d[6]})\n\nAtentamente,\nJavier Camacho"
                markdown = f"### REPORTE EJECUTIVO\n**Cliente:** {cliente_sel}\n**Fecha:** {d[0]} ({d[4]})\n\n#### 1. Análisis\n* {d[1]}\n\n#### 2. Valoración\n* ${d[2]:,.2f} {d[8]}\n* {d[3]}%\n\n#### 3. Siguiente Paso\n* {d[5]} ({d[6]})"
                
                c1, c2 = st.columns(2)
                c1.text_area("Formato Correo", correo, height=200)
                c2.text_area("Formato Word", markdown, height=200)
        else:
            st.info("Registra visitas para generar reportes.")
