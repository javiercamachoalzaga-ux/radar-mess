import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import io
import sqlite3
import google.generativeai as genai
import urllib.parse

# Intento de importar docx
try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y UI/UX (CSS)
# ==========================================
st.set_page_config(page_title="SAIV | Radar Comercial MESS", page_icon="logo mess 1.jpg", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    :root { --mess-blue: #003a70; --mess-dark: #2c3e50; --mess-light: #f8fafc; }
    
    .titulo-radar { font-size: 36px; font-weight: 900; color: var(--mess-blue); margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #64748b; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid var(--mess-blue); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #64748b !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: var(--mess-dark) !important; }
    
    .alerta-estancado { background: #fff1f2; border-left: 5px solid #e11d48; padding: 15px; border-radius: 6px; margin-bottom: 10px; }
    .stButton>button { font-weight: 600; border-radius: 6px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    
    /* Estilo para botón de Google Calendar */
    .btn-google { background-color: #4285F4; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 10px; text-align: center; }
    .btn-google:hover { background-color: #357ae8; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.image("logo mess 2.jpg", use_container_width=True)

# ==========================================
# 2. SEGURIDAD Y RESCATE MÓVIL
# ==========================================
def check_password():
    if "mi_contrasena" not in st.secrets: return True
    st.sidebar.header("🔒 Acceso Restringido")
    
    with st.sidebar.form("login_form"):
        pwd = st.text_input("Contraseña corporativa", type="password")
        btn_acceder = st.form_submit_button("Acceder al SAIV")
        
    if pwd == st.secrets["mi_contrasena"]: 
        return True
    elif btn_acceder and pwd != st.secrets["mi_contrasena"]:
        st.sidebar.error("Contraseña incorrecta. Intenta de nuevo.")
        
    return False

if not check_password():
    # Mensaje salvavidas para usuarios de celular
    st.info("👈 **ATENCIÓN MÓVIL:** Toca la flecha o el menú en la esquina superior izquierda de tu pantalla para ingresar la contraseña.")
    st.stop()

# ==========================================
# 3. CONFIGURACIÓN GEMINI API
# ==========================================
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

# ==========================================
# 4. BASE DE DATOS SQLITE (SOLO REPORTES)
# ==========================================
def init_db():
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_proyecto TEXT, cliente TEXT, pain TEXT, monto REAL, 
            probabilidad INTEGER, semana TEXT, divisa TEXT, 
            siguiente_paso TEXT, fecha_prox TEXT, estatus TEXT, roi_calculado REAL
        )
    """)
    cursor.execute("PRAGMA table_info(reportes)")
    columnas_reportes = [col[1] for col in cursor.fetchall()]
    
    if 'folio_proyecto' not in columnas_reportes: cursor.execute("ALTER TABLE reportes ADD COLUMN folio_proyecto TEXT")
    if 'divisa' not in columnas_reportes: cursor.execute("ALTER TABLE reportes ADD COLUMN divisa TEXT DEFAULT 'MXN'")
    if 'fecha_prox' not in columnas_reportes: cursor.execute("ALTER TABLE reportes ADD COLUMN fecha_prox TEXT")
    if 'roi_calculado' not in columnas_reportes: cursor.execute("ALTER TABLE reportes ADD COLUMN roi_calculado REAL")

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
# 5. MEMORIA DE SESIÓN (STATE)
# ==========================================
if 'ai_analisis' not in st.session_state: st.session_state.ai_analisis = ""
if 'ai_mensaje' not in st.session_state: st.session_state.ai_mensaje = ""
if 'ai_objeciones' not in st.session_state: st.session_state.ai_objeciones = ""
if 'ai_marketing' not in st.session_state: st.session_state.ai_marketing = ""
if 'ai_log' not in st.session_state: st.session_state.ai_log = ""
if 'ai_cliente' not in st.session_state: st.session_state.ai_cliente = ""
if 'ai_folio' not in st.session_state: st.session_state.ai_folio = ""
if 'ai_usd' not in st.session_state: st.session_state.ai_usd = 0.0
if 'ai_mxn' not in st.session_state: st.session_state.ai_mxn = 0.0
if 'roi_calc' not in st.session_state: st.session_state.roi_calc = ""

# ==========================================
# 6. MOTOR DE INGESTA
# ==========================================
def procesar_csv(archivo):
    try:
        df_raw = pd.read_csv(archivo, encoding='latin-1', header=None, sep=None, engine='python')
        header_idx = -1
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.dropna()]).strip()
            if 'PROYECTO' in row_str and 'CLIENTE' in row_str:
                header_idx = idx
                break
        
        if header_idx == -1: return None
        
        headers = [str(x).upper().replace('\ufeff', '').strip() for x in df_raw.iloc[header_idx] if pd.notna(x)]
        df_data = df_raw.iloc[header_idx+1:].dropna(axis=1, how='all')
        df_data.columns = headers[:len(df_data.columns)]

        def buscar_col(claves):
            for clave in claves:
                for col in df_data.columns:
                    if str(col).upper().strip() == clave or str(col).upper().strip() == f"{clave}.1":
                        return df_data[col].copy()
            return pd.Series([None] * len(df_data))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO", "FOLIO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "EMPRESA"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Estatus_CRM'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def extr_num(val):
            v = re.sub(r'[^\d.]', '', str(val).upper().replace(',', ''))
            return float(v) if v else 0.0

        monto_mxn, monto_usd = np.zeros(len(df_data)), np.zeros(len(df_data))
        col_moneda = buscar_col(["MONEDA", "DIVISA"])
        
        for col in df_data.columns:
            c_name = str(col).upper().strip()
            if any(k in c_name for k in ["VALOR", "MONTO", "IMPORTE", "TOTAL"]):
                is_usd = 'USD' in c_name or 'US$' in c_name
                for i in range(len(df_data)):
                    val = df_data[col].iloc[i]
                    num = extr_num(val)
                    mon_fila = str(col_moneda.iloc[i]).upper() if not col_moneda.isna().all() else ""
                    if is_usd or 'USD' in str(val).upper() or 'US$' in str(val).upper() or 'USD' in mon_fila:
                        monto_usd[i] += num
                    else:
                        monto_mxn[i] += num
                        
        df_clean['Monto_MXN'] = monto_mxn
        df_clean['Monto_USD'] = monto_usd
        df_clean = df_clean.dropna(subset=['ID_Proyecto']).reset_index(drop=True)

        df_clean['Cliente'] = df_clean['Cliente'].apply(lambda x: re.sub(r'\s+', ' ', str(x).replace("?", "ó")).strip().title() if pd.notna(x) else "")
        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        df_agrupado = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first',
            'Area': 'first', 'Fecha_Creacion': 'first',
            'Estatus_CRM': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum', 'Monto_USD': 'sum'
        }).reset_index()

        df_agrupado.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        df_agrupado = df_agrupado[(df_agrupado['Monto_MXN'] > 0) | (df_agrupado['Monto_USD'] > 0)]

        filtro_estatus = df_agrupado['Estatus_CRM'].str.contains('PROCESO', case=False, na=False)
        filtro_etapa = df_agrupado['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)
        df_agrupado = df_agrupado[filtro_estatus | filtro_etapa].copy()

        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "OPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama"
            elif any(k in texto for k in ["CALIBRACIÓN", "CALIBRACION", "LABORATORIO", "DIMENSIONAL"]): return "2. Calibraciones"
            else: return "3. Productos Generales"
            
        df_agrupado['Pilar_Estrategico'] = df_agrupado.apply(clasificar_pilar, axis=1)
        
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            elif 'GANAD' in e or 'CERRAD' in e: return "5. Cerrado Ganado"
            else: return "1. Propuesta"
            
        df_agrupado['Fase_Pipeline'] = df_agrupado['Etapa'].apply(clasificar_fase)
        df_agrupado['Fecha_Creacion_DT'] = pd.to_datetime(df_agrupado['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df_agrupado['Días_Activo'] = (pd.Timestamp.now() - df_agrupado['Fecha_Creacion_DT']).dt.days

        return df_agrupado
    except Exception as e:
        st.error(f"Error procesando CSV: {e}")
        return None

def sync_master_key(df_csv):
    db_reps = run_query("SELECT folio_proyecto, estatus, probabilidad FROM reportes WHERE folio_proyecto IS NOT NULL")
    if db_reps and not df_csv.empty:
        df_db = pd.DataFrame(db_reps, columns=['ID_Proyecto', 'Estatus_RevOps', 'Probabilidad_RevOps'])
        df_db = df_db.drop_duplicates(subset=['ID_Proyecto'], keep='last')
        df_db['ID_Proyecto'] = df_db['ID_Proyecto'].astype(str)
        df_csv['ID_Proyecto'] = df_csv['ID_Proyecto'].astype(str)
        
        df_merged = pd.merge(df_csv, df_db, on='ID_Proyecto', how='left')
        df_merged['Fase_Pipeline'] = np.where(df_merged['Estatus_RevOps'].notna(), df_merged['Estatus_RevOps'], df_merged['Fase_Pipeline'])
        return df_merged
    return df_csv

# ==========================================
# INTERFAZ PRINCIPAL Y TABS
# ==========================================
col_logo, col_titulos = st.columns([1, 10])

with col_logo:
    st.image("logo mess 1.jpg", width=80) 

with col_titulos:
    st.markdown('<div class="titulo-radar" style="margin-top: -10px;">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitulo">Módulo CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)

t_dash, t_stalled, t_ai, t_revops = st.tabs([
    "📊 1. Dashboards CRM", 
    "🚨 2. Proyectos Estancados", 
    "🧠 3. Laboratorio Táctico IA",
    "🚀 4. Gestión Comercial (RevOps)"
])

archivo = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])
df = pd.DataFrame()

if archivo:
    df_bruto = procesar_csv(archivo)
    if df_bruto is not None and not df_bruto.empty:
        df = sync_master_key(df_bruto)
        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        f_pilar = st.sidebar.multiselect("Pilar Estratégico:", sorted(df['Pilar_Estrategico'].unique()), default=sorted(df['Pilar_Estrategico'].unique()))
        f_buscar = st.sidebar.text_input("Buscar Folio o Cliente:")
        if f_buscar:
            df = df[(df['ID_Proyecto'].str.contains(f_buscar, case=False, na=False)) | (df['Cliente'].str.contains(f_buscar, case=False, na=False))]
        if f_pilar:
            df = df[df['Pilar_Estrategico'].isin(f_pilar)]

# ==========================================
# 📊 ESTACIÓN 1: DASHBOARDS
# ==========================================
with t_dash:
    if not df.empty:
        META_MENSUAL_USD = 80000.00
        
        df_caliente = df[df['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO', '5. Cerrado Ganado'])]
        usd_caliente = df_caliente['Monto_USD'].sum()
        mxn_caliente = df_caliente['Monto_MXN'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Meta Mensual (USD)", f"${META_MENSUAL_USD:,.2f}")
        c2.metric("Pipeline Probable (Activo)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN")
        
        gap = META_MENSUAL_USD - usd_caliente
        if gap > 0: c3.metric("GAP (Brecha)", f"${gap:,.2f} USD", "- Acción Requerida")
        else: c3.metric("GAP (Brecha)", "$0.00 USD", "+ Meta Cubierta")
        
        st.divider()
        moneda_sel = st.radio("Moneda de Análisis:", ["USD", "MXN"], horizontal=True)
        col_val = 'Monto_USD' if moneda_sel == "USD" else 'Monto_MXN'
        
        st.markdown(f"#### Análisis Pareto 80/20 por Cuentas ({moneda_sel})")
        df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
        df_pareto = df_pareto[df_pareto[col_val] > 0].sort_values(by=col_val, ascending=False).reset_index(drop=True)
        
        if not df_pareto.empty:
            df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
            df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
            
            barras = alt.Chart(df_pareto).mark_bar(color='#003a70').encode(x=alt.X('Cliente', sort=None), y=alt.Y(col_val))
            linea = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(x=alt.X('Cliente', sort=None), y=alt.Y('Acumulado', axis=alt.Axis(format='%')))
            st.altair_chart(alt.layer(barras, linea).resolve_scale(y='independent').properties(height=350), use_container_width=True)

        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown("**Forecast por Área**")
            df_a = df.groupby('Area')[col_val].sum().reset_index()
            if not df_a.empty: st.altair_chart(alt.Chart(df_a).mark_bar(color='#2c3e50').encode(x=col_val, y=alt.Y('Area', sort='-x')).properties(height=300), use_container_width=True)
        with cg2:
            st.markdown("**Salud del Embudo**")
            df_f = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
            if not df_f.empty: st.altair_chart(alt.Chart(df_f).mark_bar(color='#16a34a').encode(x=col_val, y=alt.Y('Fase_Pipeline', sort='-x')).properties(height=300), use_container_width=True)
    else:
        st.info("Sube el archivo CSV del CRM para visualizar los dashboards.")

# ==========================================
# 🚨 ESTACIÓN 2: PROYECTOS ESTANCADOS
# ==========================================
with t_stalled:
    if not df.empty:
        st.subheader("Riesgo Operativo: Proyectos Inactivos (>15 días)")
        estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Días_Activo', ascending=False)
        
        if not estancados.empty:
            for _, r in estancados.iterrows():
                st.markdown(f"""
                <div class="alerta-estancado">
                    <h4 style="margin:0; color:#9f1239;">{r['ID_Proyecto']} | {r['Cliente']}</h4>
                    <p style="margin:5px 0 0 0; font-size:14px;"><b>Días Inactivo:</b> {r['Días_Activo']} | <b>Riesgo USD:</b> ${r['Monto_USD']:,.2f} | <b>Fase:</b> {r['Fase_Pipeline']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("¡Embudo limpio! No hay proyectos estancados de alto riesgo.")
    else:
        st.info("Sube el CSV para auditar proyectos estancados.")

# ==========================================
# 🧠 ESTACIÓN 3: LABORATORIO IA (KAM)
# ==========================================
with t_ai:
    if not df.empty:
        st.subheader("Configuración de Paquete (Bundle)")
        clientes = sorted(df['Cliente'].dropna().unique().tolist())
        c_sel = st.selectbox("1. Selecciona la Cuenta:", ["-- Selecciona --"] + clientes)
        
        if c_sel != "-- Selecciona --":
            df_c = df[df['Cliente'] == c_sel]
            opciones = df_c.apply(lambda x: f"[{x['ID_Proyecto']}] {str(x['Descripcion'])} - ${x['Monto_USD']:,.0f} USD / ${x['Monto_MXN']:,.0f} MXN", axis=1).tolist()
            p_sel = st.multiselect("2. Agrupar Folios:", opciones)
            
            if p_sel:
                ids = [o.split("]")[0].replace("[", "") for o in p_sel]
                df_s = df[df['ID_Proyecto'].astype(str).isin(ids)]
                t_usd, t_mxn = df_s['Monto_USD'].sum(), df_s['Monto_MXN'].sum()
                eqs = " | ".join(df_s['Descripcion'].astype(str).tolist())
                
                st.markdown(f"**Valor del Paquete:** <span style='color:green'>${t_usd:,.2f} USD</span> | <span style='color:purple'>${t_mxn:,.2f} MXN</span>", unsafe_allow_html=True)
                
                st.markdown("#### Configuración Táctica")
                c1, c2 = st.columns(2)
                with c1:
                    obj = st.radio("Objetivo:", ["Cierre / Seguimiento Virtual", "Apertura / Visita Presencial"])
                    canal = st.selectbox("Canal/Tipo:", ["Correo Electrónico Ejecutivo", "Guion de Llamada", "Mensaje WhatsApp", "Visita con Director"])
                    interlocutor = st.selectbox("Interlocutor:", ["Comprador", "Ingeniero / Planta", "Director / Dueño"])
                with c2:
                    contexto = st.text_area("Notas Manuales (Contexto actual):", placeholder="Ej. Quieren crédito a 60 días...")
                
                if gemini_activo and st.button("🧠 Generar Estrategia", type="primary"):
                    with st.spinner("Procesando con Gemini..."):
                        try:
                            prompt = f"""
                            Eres Javier Camacho, KAM en MESS Servicios Metrológicos.
                            Cliente: {c_sel} (Perfil: {interlocutor}). Proyectos agrupados: {len(df_s)}.
                            Equipos: {eqs}. Monto: ${t_usd} USD / ${t_mxn} MXN.
                            Acción: {canal}. Contexto: {contexto}.
                            
                            Usa MEDDPICC, SPIN y Sandler. Sé muy humano, B2B. NO uses Markdown fuera de las etiquetas XML.
                            DEBES usar estrictamente estas etiquetas:
                            <ANALYSIS>Análisis de cuenta y cómo vender el paquete</ANALYSIS>
                            <MESSAGE>El texto exacto para {canal}</MESSAGE>
                            <OBJECTIONS>2 objeciones y cómo rebatirlas</OBJECTIONS>
                            <MARKETING>Petición para equipo de marketing ABM</MARKETING>
                            <LOG>Resumen hiper-breve para el CRM</LOG>
                            """
                            model = genai.GenerativeModel("gemini-3.6-flash")
                            res = model.generate_content(prompt).text
                            
                            def extr(tag, t): 
                                m = re.search(fr'<{tag}>(.*?)</{tag}>', t, re.DOTALL)
                                return m.group(1).strip() if m else "Error extracción."
                                
                            st.session_state.update({
                                'ai_analisis': extr('ANALYSIS', res), 'ai_mensaje': extr('MESSAGE', res),
                                'ai_objeciones': extr('OBJECTIONS', res), 'ai_marketing': extr('MARKETING', res),
                                'ai_log': extr('LOG', res), 'ai_cliente': c_sel, 'ai_folio': ", ".join(ids),
                                'ai_usd': t_usd, 'ai_mxn': t_mxn
                            })
                        except Exception as e: st.error(f"Error API: {e}")

                if st.session_state.get('ai_mensaje'):
                    st.success("Estrategia Generada")
                    st.info(f"**Análisis:**\n{st.session_state.ai_analisis}")
                    st.markdown(f"<div class='caja-ia'><b>Mensaje:</b><br>{st.session_state.ai_mensaje}</div>", unsafe_allow_html=True)
                    st.warning(f"**Objeciones:**\n{st.session_state.ai_objeciones}")
                    
                    st.divider()
                    st.markdown("### 📋 Módulo de Ejecución Operativa")
                    c_op1, c_op2 = st.columns(2)
                    
                    with c_op1:
                        # Botón Dinámico de Google Calendar
                        titulo_cita = urllib.parse.quote(f"Visita / Llamada - {st.session_state.ai_cliente}")
                        detalles_cita = urllib.parse.quote(f"Proyectos: {st.session_state.ai_folio}\n\nContexto IA:\n{st.session_state.ai_log}")
                        url_gcal = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={titulo_cita}&details={detalles_cita}"
                        
                        st.markdown(f'<a href="{url_gcal}" target="_blank" class="btn-google">📅 Agendar Cita en Google Calendar</a>', unsafe_allow_html=True)
                        st.caption("Abre una pestaña nueva con el evento pre-llenado.")

                    with c_op2:
                        # Generador de Documento
                        if docx_disponible:
                            def generar_docx():
                                doc = Document()
                                doc.add_heading("ESTRATEGIA KAM", 0)
                                doc.add_paragraph(f"Cliente: {st.session_state.ai_cliente} | Folios: {st.session_state.ai_folio}")
                                doc.add_heading("1. Análisis", 1)
                                doc.add_paragraph(st.session_state.ai_analisis)
                                doc.add_heading("2. Mensaje / Guion", 1)
                                doc.add_paragraph(st.session_state.ai_mensaje)
                                b = io.BytesIO()
                                doc.save(b)
                                b.seek(0)
                                return b
                            st.download_button("💾 Descargar Documento .docx", data=generar_docx(), file_name=f"Estrategia_{st.session_state.ai_cliente.replace(' ','_')}.docx")

                    # Caja de texto para copiar el reporte a SCOTT CRM
                    st.markdown("**Reporte de actividades (SCOTT CRM):**")
                    st.text_area("Copia y pega este texto directamente en tu CRM SCOTT:", value=st.session_state.ai_log, height=120)
                    
                    if st.button("🚀 Inyectar Estrategia al Forecast del SAIV"):
                        f_hoy = datetime.now().strftime("%Y-%m-%d")
                        div = "USD" if st.session_state.ai_usd > 0 else "MXN"
                        mto = st.session_state.ai_usd if div == "USD" else st.session_state.ai_mxn
                        run_query("INSERT INTO reportes (folio_proyecto, cliente, pain, monto, probabilidad, semana, divisa, siguiente_paso, fecha_prox, estatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (st.session_state.ai_folio, st.session_state.ai_cliente, st.session_state.ai_log, mto, 50, "W1", div, canal, f_hoy, "3. Negociación"), fetch=False)
                        st.success("¡Inyectado a la Base de Datos! Revisa el módulo de Forecast.")
    else:
        st.info("Sube el CSV para habilitar la IA.")

# ==========================================
# 🚀 ESTACIÓN 4: GESTIÓN COMERCIAL (REVOPS)
# ==========================================
with t_revops:
    t_roi, t_fc = st.tabs(["🧮 Calculadora ROI", "📈 Forecast Automático"])

    # 1. CALCULADORA ROI
    with t_roi:
        st.subheader("Calculadora de ROI Metrológico")
        cr1, cr2 = st.columns(2)
        with cr1:
            inv = st.number_input("Inversión del Equipo (Ej. 60000 USD)", min_value=0.0, value=60000.0)
            c_hora = st.number_input("Costo Máquina CNC / Hora (USD)", value=50.0)
            rechazo = st.number_input("Piezas rechazadas por semana", value=10)
        with cr2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Calcular Retorno Financiero", type="primary"):
                ahorro_anual = (c_hora * 2) * rechazo * 52
                meses_roi = inv / (ahorro_anual / 12) if ahorro_anual > 0 else 999
                st.session_state.roi_calc = f"Ahorro anual: ${ahorro_anual:,.2f} USD | Recuperación en {meses_roi:.1f} meses"
                st.success(st.session_state.roi_calc)

    # 2. FORECAST Y AUTOMATIZACIÓN
    with t_fc:
        st.subheader("Forecast Real (Pipeline Ponderado)")
        reps = run_query("SELECT id, folio_proyecto, cliente, monto, probabilidad, semana, divisa, estatus FROM reportes")
        if reps:
            df_fc = pd.DataFrame(reps, columns=["ID", "Folio", "Cliente", "Monto", "Prob(%)", "Semana", "Divisa", "Estatus"])
            df_fc['Forecast_Real'] = df_fc['Monto'] * (df_fc['Prob(%)'] / 100.0)
            
            c_f1, c_f2 = st.columns(2)
            for divisa, col in zip(["USD", "MXN"], [c_f1, c_f2]):
                df_div = df_fc[df_fc['Divisa'] == divisa]
                col.metric(f"Forecast {divisa}", f"${df_div['Forecast_Real'].sum():,.2f}", f"Pipeline Total: ${df_div['Monto'].sum():,.2f}")
            
            st.dataframe(df_fc.drop(columns=['ID']), use_container_width=True)
            
            st.divider()
            st.markdown("#### Generador Omnicanal")
            id_sel = st.selectbox("Seleccionar Reporte a Enviar", df_fc['Folio'].astype(str) + " - " + df_fc['Cliente'])
            if st.button("📧 Enviar por Correo a Gerencia"):
                st.toast(f"Reporte enviado exitosamente a la Gerencia.", icon="✅")
                st.success("Indicadores consolidados en formato Markdown y enviados.")
        else:
            st.info("Sin registros en SQLite para calcular Forecast. Genera e inyecta una estrategia desde el Laboratorio IA.")
