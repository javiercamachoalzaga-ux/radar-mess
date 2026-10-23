import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import io
import json
import sqlite3
import google.generativeai as genai
import urllib.parse

try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide", initial_sidebar_state="expanded")

if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

def init_db():
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS agenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, horario TEXT DEFAULT '09:00',
        cliente TEXT, contacto TEXT, objetivo TEXT, estatus TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reportes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_rep TEXT, cliente TEXT, resumen TEXT,
        pain TEXT, monto REAL, probabilidad INTEGER, semana TEXT, siguiente_paso TEXT, 
        proxima_fecha TEXT, estatus TEXT, moneda TEXT DEFAULT 'MXN')''')
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

if 'tactica_analisis' not in st.session_state: st.session_state.tactica_analisis = ""
if 'tactica_mensaje' not in st.session_state: st.session_state.tactica_mensaje = ""
if 'tactica_objeciones' not in st.session_state: st.session_state.tactica_objeciones = ""
if 'tactica_marketing' not in st.session_state: st.session_state.tactica_marketing = ""
if 'tactica_bitacora' not in st.session_state: st.session_state.tactica_bitacora = ""
if 'tactica_cliente' not in st.session_state: st.session_state.tactica_cliente = ""
if 'tactica_id' not in st.session_state: st.session_state.tactica_id = ""
if 'tactica_equipo' not in st.session_state: st.session_state.tactica_equipo = ""
if 'tactica_monto' not in st.session_state: st.session_state.tactica_monto = ""
if 'monto_usd_ia' not in st.session_state: st.session_state.monto_usd_ia = 0.0
if 'monto_mxn_ia' not in st.session_state: st.session_state.monto_mxn_ia = 0.0

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo-radar { font-size: 38px; font-weight: 900; color: #003a70; margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #555555; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #7f8c8d !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important; }
    .ficha-scott { background-color: #f4f6f7; padding: 20px; border-radius: 8px; border: 1px solid #d5d8dc; margin-bottom: 20px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

def check_password():
    if "mi_contrasena" not in st.secrets: return True
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña corporativa", type="password")
    if pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral para acceder al sistema.")
    st.stop()

st.markdown('<div class="titulo-radar">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Módulo CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)

tab_dashboards, tab_scott = st.tabs([
    "1. Dashboards CRM", "2. Laboratorio IA (Estrategia Integral)"
])

@st.cache_data
def procesar_csv(file_bytes):
    try:
        try:
            df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding='utf-8-sig', header=None, sep=None, engine='python')
        except UnicodeDecodeError:
            df_raw = pd.read_csv(io.BytesIO(file_bytes), encoding='latin-1', header=None, sep=None, engine='python')

        header_idx = -1
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.dropna()]).strip()
            if 'PROYECTO' in row_str and 'CLIENTE' in row_str:
                header_idx = idx
                break
        if header_idx == -1: return None
        
        headers = [str(x).upper().replace('\ufeff', '').strip() for x in df_raw.iloc[header_idx] if pd.notna(x)]
        df_data = df_raw.iloc[header_idx+1:].copy().dropna(axis=1, how='all')
        df_data.columns = headers[:len(df_data.columns)]

        def buscar_col(claves):
            for clave in claves:
                for col in df_data.columns:
                    col_limpia = str(col).upper().strip()
                    if col_limpia == clave or col_limpia == f"{clave}.1":
                        return df_data[col].copy()
            return pd.Series([None] * len(df_data))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO", "FOLIO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "EMPRESA"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def extr_num(val_str):
            try:
                v = str(val_str).upper().replace('$', '').replace('USD', '').replace('MXN', '').replace(' ', '').strip()
                if ',' in v and '.' in v: v = v.replace(',', '')
                elif ',' in v and len(v.split(',')[-1]) != 2: v = v.replace(',', '')
                elif ',' in v and len(v.split(',')[-1]) == 2: v = v.replace(',', '.')
                v = ''.join(c for c in v if c.isdigit() or c == '.')
                return float(v) if v else 0.0
            except: return 0.0

        monto_mxn, monto_usd = np.zeros(len(df_data)), np.zeros(len(df_data))
        col_moneda = buscar_col(["MONEDA", "DIVISA"])
        
        for col in df_data.columns:
            col_name = str(col).upper().strip()
            if any(k in col_name for k in ["VALOR", "MONTO", "IMPORTE", "TOTAL"]):
                is_col_usd = 'USD' in col_name or 'US$' in col_name
                for i in range(len(df_data)):
                    val_raw = df_data[col].iloc[i]
                    val_str = str(val_raw).upper()
                    num = extr_num(val_raw)
                    moneda_fila = str(col_moneda.iloc[i]).upper() if not col_moneda.isna().all() else ""
                    if is_col_usd or 'USD' in val_str or 'US$' in val_str or 'USD' in moneda_fila or 'US$' in moneda_fila or 'DÓLA' in moneda_fila:
                        monto_usd[i] += num
                    else:
                        monto_mxn[i] += num
                        
        df_clean['Monto_MXN'] = monto_mxn
        df_clean['Monto_USD'] = monto_usd
        df_clean = df_clean.dropna(subset=['ID_Proyecto']).reset_index(drop=True)
        
        def limpiar_cliente(texto):
            if pd.isna(texto): return ""
            return re.sub(r'\s+', ' ', str(texto).replace("?", "ó")).strip().title()
            
        df_clean['Cliente'] = df_clean['Cliente'].apply(limpiar_cliente)
        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        df_g = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first', 'Area': 'first', 'Fecha_Creacion': 'first',
            'Estatus': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum', 'Monto_USD': 'sum'
        }).reset_index()

        df_g.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        
        filtro_etapa = df_g['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)
        filtro_monto = (df_g['Monto_MXN'] > 0) | (df_g['Monto_USD'] > 0)
        df_g = df_g[filtro_etapa | filtro_monto].copy()

        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama"
            elif any(k in texto for k in ["CALIBRACIÓN", "LABORATORIO", "DIMENSIONAL"]): return "2. Calibraciones"
            else: return "3. Productos Generales"
            
        df_g['Pilar_Estrategico'] = df_g.apply(clasificar_pilar, axis=1)
        
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            else: return "5. En Proceso"
            
        df_g['Fase_Pipeline'] = df_g['Etapa'].apply(clasificar_fase)
        df_g['Fecha_Creacion_DT'] = pd.to_datetime(df_g['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df_g['Fecha_Cierre_DT'] = pd.to_datetime(df_g['Fecha_Cierre'], errors='coerce', dayfirst=True)
        df_g['Días_Activo'] = (pd.Timestamp.now() - df_g['Fecha_Creacion_DT']).dt.days

        return df_g, None
    except Exception as e:
        return pd.DataFrame(), str(e)

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])
df = pd.DataFrame()

if archivo_cargado is not None:
    file_bytes = archivo_cargado.getvalue()
    df_proc, error_msg = procesar_csv(file_bytes)
    
    if error_msg:
        st.sidebar.error(f"Error procesando CSV: {error_msg}")
    elif df_proc is not None and not df_proc.empty:
        df = df_proc.copy()
        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        opc_pilar = df['Pilar_Estrategico'].unique().tolist()
        f_pilar = st.sidebar.multiselect("Filtrar por Pilar:", opc_pilar, default=opc_pilar)
        f_busq = st.sidebar.text_input("Buscar Folio o Cliente:")
        
        if f_busq:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(f_busq, case=False, na=False)) | 
                    (df['Cliente'].str.contains(f_busq, case=False, na=False))]
        if f_pilar:
            df = df[df['Pilar_Estrategico'].isin(f_pilar)]
    elif df_proc is None or df_proc.empty:
        st.sidebar.warning("El archivo se leyó pero no se encontraron proyectos con montos y etapas activas.")

# TAB 1: DASHBOARDS
with tab_dashboards:
    if not df.empty:
        st.markdown("### Análisis de Forecast vs Cuota ($80K USD)")
        META_MENSUAL_USD = 80000.00
        
        df_caliente = df[df['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]
        usd_caliente = df_caliente['Monto_USD'].sum()
        mxn_caliente = df_caliente['Monto_MXN'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Meta Comercial Mensual", f"${META_MENSUAL_USD:,.2f} USD")
        c2.metric("Pipeline Probable (Activo)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN extra")
        if (META_MENSUAL_USD - usd_caliente) > 0:
            c3.metric("GAP (Brecha para Meta)", f"${(META_MENSUAL_USD - usd_caliente):,.2f} USD", "- Acción requerida")
        else:
            c3.metric("GAP (Brecha)", "$0.00 USD", "+ Meta Cubierta")
        
        st.divider()
        c_sel1, c_sel2 = st.columns([1, 3])
        with c_sel1: moneda_sel = st.selectbox("Seleccionar Moneda para Gráficos:", ["USD ($)", "MXN ($)"])
        col_val = 'Monto_USD' if moneda_sel == "USD ($)" else 'Monto_MXN'
        
        st.divider()
        st.markdown(f"#### Análisis Pareto 80/20 por Cuentas Clave ({moneda_sel})")
        df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
        df_pareto = df_pareto[df_pareto[col_val] > 0].sort_values(by=col_val, ascending=False).reset_index(drop=True)
        
        if not df_pareto.empty:
            df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
            df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
            
            barras = alt.Chart(df_pareto).mark_bar(color='#34495e').encode(
                x=alt.X('Cliente', sort=None, axis=alt.Axis(labelLimit=0)), y=alt.Y(col_val)
            )
            linea = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(
                x=alt.X('Cliente', sort=None), y=alt.Y('Acumulado', axis=alt.Axis(format='%'))
            )
            st.altair_chart(alt.layer(barras, linea).resolve_scale(y='independent').properties(height=450), use_container_width=True)
        
        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**Forecast por Área**")
            df_a = df.groupby('Area')[col_val].sum().reset_index()
            if not df_a.empty: st.altair_chart(alt.Chart(df_a[df_a[col_val]>0]).mark_bar(color='#003a70').encode(x=alt.X(col_val), y=alt.Y('Area', sort='-x')).properties(height=350), use_container_width=True)
        with col_g2:
            st.markdown("**Salud del Embudo**")
            df_f = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
            if not df_f.empty: st.altair_chart(alt.Chart(df_f[df_f[col_val]>0]).mark_bar(color='#2ecc71').encode(x=alt.X(col_val), y=alt.Y('Fase_Pipeline', sort='-x')).properties(height=350), use_container_width=True)
    else:
        st.info("Sube el archivo CSV del CRM SCOTT en la barra lateral para ver tus datos.")

# TAB 2: LABORATORIO IA
with tab_scott:
    if not df.empty:
        st.markdown("### Copiloto Estratégico (Key Account Management)")
        c_disp = sorted(df['Cliente'].unique().tolist())
        c_sel = st.selectbox("1. Selecciona la Cuenta / Cliente:", ["-- Selecciona --"] + c_disp)
        
        if c_sel != "-- Selecciona --":
            df_c = df[df['Cliente'] == c_sel]
            opciones = df_c.apply(lambda x: f"[{x['ID_Proyecto']}] {str(x['Descripcion'])} - ${x['Monto_USD']:,.0f} USD / ${x['Monto_MXN']:,.0f} MXN", axis=1).tolist()
            p_sel = st.multiselect("2. Folios a incluir:", opciones)
            
            if p_sel:
                ids = [o.split("]")[0].replace("[", "") for o in p_sel]
                df_s = df[df['ID_Proyecto'].astype(str).isin(ids)]
                
                t_usd, t_mxn = df_s['Monto_USD'].sum(), df_s['Monto_MXN'].sum()
                eqs = " | ".join(df_s['Descripcion'].tolist())
                ids_str = ", ".join(df_s['ID_Proyecto'].astype(str).tolist())
                
                st.session_state.monto_usd_ia = t_usd
                st.session_state.monto_mxn_ia = t_mxn
                
                st.markdown(f"""
                <div class="ficha-scott">
                    <h4>{c_sel} (Folios: {ids_str})</h4>
                    <b>Equipos Involucrados:</b> <span style='color:#003a70;'>{eqs}</span><br>
                    <b>Monto Total a Negociar:</b> <span style='color:#27ae60; font-weight:bold; font-size:18px;'>${t_usd:,.2f} USD</span> | <span style='color:#8e44ad; font-weight:bold;'>${t_mxn:,.2f} MXN</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### Configuración Táctica")
                t_op = st.radio("Objetivo:", ["Aceleración y Cierre (Virtual)", "Apertura y Visitas (Presencial)"], horizontal=True)

                c1, c2 = st.columns(2)
                with c1:
                    if t_op == "Aceleración y Cierre (Virtual)": sub_op = st.radio("Canal:", ["Mensaje de WhatsApp", "Correo Electrónico Ejecutivo", "Guion de Llamada"])
                    else: sub_op = st.radio("Tipo visita:", ["Prospección", "Técnica", "Estratégica (Gerencia)"])
                    interlocutor = st.selectbox("Perfil:", ["Ingeniero / Calidad", "Comprador", "Director / Dueño"])
                with c2: 
                    giro = st.text_input("Giro (Ej. Aeroespacial):")
                    contexto = st.text_area("Contexto actual:", height=100)
                
                if gemini_activo and st.button("🧠 Generar Estrategia", type="primary", use_container_width=True):
                    with st.spinner("Diseñando estrategia..."):
                        try:
                            model = genai.GenerativeModel("gemini-pro")
                            prompt = f"Cliente: {c_sel}. Interlocutor: {interlocutor}. Equipos: {eqs}. Monto: ${t_usd} USD. Acción: {sub_op}. Giro: {giro}. Notas: {contexto}. Eres KAM de MESS. Aplica MEDDPICC, SPIN, Sandler. Usa etiquetas <ANALYSIS> <MESSAGE> <OBJECTIONS> <MARKETING> <LOG> y dentro escribe en español."
                            res = model.generate_content(prompt).text
                            
                            def ext(tag, txt):
                                m = re.search(fr'<{tag}[^>]*>(.*?)</{tag}>', txt, re.DOTALL | re.IGNORECASE)
                                return m.group(1).strip() if m else ""
                                
                            st.session_state.tactica_analisis = ext('ANALYSIS', res)
                            st.session_state.tactica_mensaje = ext('MESSAGE', res)
                            st.session_state.tactica_objeciones = ext('OBJECTIONS', res)
                            st.session_state.tactica_marketing = ext('MARKETING', res)
                            st.session_state.tactica_bitacora = ext('LOG', res)
                            
                            st.session_state.tactica_cliente = c_sel
                            st.session_state.tactica_id = ids_str
                            st.session_state.tactica_equipo = eqs
                            st.session_state.tactica_monto = f"${t_usd:,.2f} USD / ${t_mxn:,.2f} MXN"
                        except Exception as e:
                            st.error(f"Error IA: {e}")

                if st.session_state.tactica_mensaje:
                    st.success("Estrategia Generada")
                    st.info(st.session_state.tactica_analisis)
                    st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_mensaje}</div>", unsafe_allow_html=True)
                    st.warning(st.session_state.tactica_objeciones)
                    st.info(st.session_state.tactica_marketing)
                    st.success(st.session_state.tactica_bitacora)
                            
                    if docx_disponible:
                        st.divider()
                        st.markdown("### 📤 Exportar Documento")
                        def exp_docx():
                            doc = Document()
                            doc.add_heading("ESTRATEGIA KAM", 0)
                            doc.add_paragraph(f"Cliente: {st.session_state.tactica_cliente}")
                            doc.add_paragraph(st.session_state.tactica_analisis)
                            doc.add_paragraph(st.session_state.tactica_mensaje)
                            b = io.BytesIO()
                            doc.save(b)
                            b.seek(0)
                            return b
                        st.download_button("Descargar .docx", data=exp_docx(), file_name="Estrategia.docx")
    else:
        st.info("Requiere datos.")
