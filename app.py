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

try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

st.set_page_config(
    page_title="SAIV | Radar Comercial MESS", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    :root { --mess-blue: #003a70; --mess-dark: #2c3e50; --mess-light: #f8fafc; }
    .titulo-radar { font-size: 36px; font-weight: 900; color: var(--mess-blue); margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #64748b; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid var(--mess-blue); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #64748b !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: var(--mess-dark) !important; }
    .alerta-estancado { background: #fff1f2; border-left: 5px solid #e11d48; padding: 15px; border-radius: 6px; margin-bottom: 5px; }
    .stButton>button { font-weight: 600; border-radius: 6px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    .caja-abm { background-color: #f8fafc; padding: 15px; border-radius: 5px; border-left: 4px solid #8b5cf6; margin-bottom: 15px; border: 1px solid #e2e8f0;}
    .btn-google { background-color: #4285F4; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 5px; text-align: center; width: 100%; }
    .btn-wa { background-color: #25D366; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 5px; text-align: center; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

col_titulos, col_vacia = st.columns([10, 1])
with col_titulos:
    st.markdown('<div class="titulo-radar" style="margin-top: 10px;">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitulo">Módulo CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)

def check_password():
    if "mi_contrasena" not in st.secrets: return True
    if st.session_state.get("autenticado", False): return True
    
    st.markdown("---")
    st.markdown("### Acceso Restringido")
    with st.form("login_form"):
        pwd = st.text_input("Ingresa tu contraseña corporativa", type="password")
        btn_acceder = st.form_submit_button("Acceder al SAIV")
        
    if btn_acceder:
        if pwd == st.secrets["mi_contrasena"]:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta. Intenta de nuevo.")
    return False

if not check_password():
    st.stop()

if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

vars_txt = ['ai_analisis', 'ai_mensaje', 'ai_objeciones', 'ai_marketing', 'ai_log', 'ai_cliente', 'ai_folio', 'roi_calc']
for v in vars_txt:
    if v not in st.session_state: st.session_state[v] = ""
for nv in ['ai_usd', 'ai_mxn']:
    if nv not in st.session_state: st.session_state[nv] = 0.0

def init_db():
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS reportes (id INTEGER PRIMARY KEY AUTOINCREMENT, folio_proyecto TEXT, cliente TEXT, pain TEXT, monto REAL, probabilidad INTEGER, semana TEXT, divisa TEXT, siguiente_paso TEXT, fecha_prox TEXT, estatus TEXT, roi_calculado REAL)")
    cursor.execute("PRAGMA table_info(reportes)")
    columnas = [col[1] for col in cursor.fetchall()]
    if 'folio_proyecto' not in columnas: cursor.execute("ALTER TABLE reportes ADD COLUMN folio_proyecto TEXT")
    if 'divisa' not in columnas: cursor.execute("ALTER TABLE reportes ADD COLUMN divisa TEXT DEFAULT 'MXN'")
    if 'fecha_prox' not in columnas: cursor.execute("ALTER TABLE reportes ADD COLUMN fecha_prox TEXT")
    if 'roi_calculado' not in columnas: cursor.execute("ALTER TABLE reportes ADD COLUMN roi_calculado REAL")
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

def ejecutar_ia(cliente, interlocutor, num_proy, eqs, t_usd, t_mxn, obj_tactico, canal, contexto):
    prompt = (
        f"Eres Javier Camacho, KAM en MESS Servicios Metrológicos. "
        f"Cliente: {cliente} (Interlocutor: {interlocutor}). Proyectos agrupados: {num_proy}. "
        f"Equipos/Servicios: {eqs}. Monto: ${t_usd:,.2f} USD / ${t_mxn:,.2f} MXN. "
        f"Objetivo Estratégico: {obj_tactico}. Modalidad / Canal de Acción: {canal}. "
        f"Contexto táctico: {contexto}. "
        f"Si la acción incluye Visita con Acompañamiento o Director, estructura el plan considerando el rol ejecutivo de respaldo gerencial/directivo para destrabar o cerrar la cuenta. "
        f"Fusiona MEDDPICC, SPIN y Sandler de forma invisible, tono humano, conversacional y directo B2B. "
        f"NO uses Markdown fuera de las etiquetas XML. "
        f"DEBES usar estrictamente estas 5 etiquetas: "
        f"<ANALYSIS>Análisis estratégico para '{obj_tactico}' y cómo vender el paquete</ANALYSIS> "
        f"<MESSAGE>El texto o guion exacto para {canal}</MESSAGE> "
        f"<OBJECTIONS>2 posibles objeciones y cómo rebatirlas</OBJECTIONS> "
        f"<MARKETING>Solicitud concreta de Account-Based Marketing (ABM) para esta cuenta</MARKETING> "
        f"<LOG>Bitácora hiper-resumida de 2 líneas para el CRM SCOTT</LOG>"
    )
    model = genai.GenerativeModel("gemini-pro")
    res = model.generate_content(prompt).text
    def extr(tag, t): 
        m = re.search(fr'<{tag}>(.*?)</{tag}>', t, re.DOTALL)
        return m.group(1).strip() if m else "Sin datos."
    return {
        'ai_analisis': extr('ANALYSIS', res),
        'ai_mensaje': extr('MESSAGE', res),
        'ai_objeciones': extr('OBJECTIONS', res),
        'ai_marketing': extr('MARKETING', res),
        'ai_log': extr('LOG', res)
    }

def mostrar_resultados_ia(canal_actual="Seguimiento"):
    if st.session_state.get('ai_mensaje'):
        st.success(f"Estrategia Generada para: {st.session_state.ai_cliente} (Folios: {st.session_state.ai_folio})")
        st.info(f"**1. Análisis Estratégico (Bundle):**\n\n{st.session_state.ai_analisis}")
        
        msj_html = f"<div class='caja-ia'><b>2. Mensaje / Guion de Contacto:</b><br><br>{st.session_state.ai_mensaje}</div>"
        st.markdown(msj_html, unsafe_allow_html=True)
        
        st.warning(f"**3. Manejo de Objeciones:**\n\n{st.session_state.ai_objeciones}")
        
        abm_html = f"<div class='caja-abm'><b>4. Solicitud Account-Based Marketing (ABM):</b><br><br>{st.session_state.ai_marketing}</div>"
        st.markdown(abm_html, unsafe_allow_html=True)
        
        st.divider()
        st.markdown("### Módulo de Ejecución Rápida")
        c_op1, c_op2, c_op3 = st.columns(3)
        
        with c_op1:
            txt_wa = urllib.parse.quote(st.session_state.ai_mensaje)
            url_wa = f"https://wa.me/?text={txt_wa}"
            st.markdown(f'<a href="{url_wa}" target="_blank" class="btn-wa">Enviar por WhatsApp</a>', unsafe_allow_html=True)
            
        with c_op2:
            titulo_cita = urllib.parse.quote(f"Visita / Seguimiento MESS - {st.session_state.ai_cliente}")
            detalles_cita = urllib.parse.quote(f"Folios: {st.session_state.ai_folio}\n\nBitácora:\n{st.session_state.ai_log}")
            url_gcal = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={titulo_cita}&details={detalles_cita}"
            st.markdown(f'<a href="{url_gcal}" target="_blank" class="btn-google">Agendar en Calendar</a>', unsafe_allow_html=True)

        with c_op3:
            if docx_disponible:
                def generar_docx():
                    doc = Document()
                    doc.add_heading("PLAN DE ATAQUE KAM - MESS", 0)
                    doc.add_paragraph(f"Cliente: {st.session_state.ai_cliente} | Folios: {st.session_state.ai_folio}")
                    doc.add_heading("1. Análisis Estratégico", 1)
                    doc.add_paragraph(st.session_state.ai_analisis)
                    doc.add_heading("2. Guion / Mensaje", 1)
                    doc.add_paragraph(st.session_state.ai_mensaje)
                    doc.add_heading("3. Objeciones", 1)
                    doc.add_paragraph(st.session_state.ai_objeciones)
                    doc.add_heading("4. Solicitud ABM", 1)
                    doc.add_paragraph(st.session_state.ai_marketing)
                    b = io.BytesIO()
                    doc.save(b)
                    b.seek(0)
                    return b
                st.download_button("Descargar Ficha .docx", data=generar_docx(), file_name=f"Plan_{st.session_state.ai_cliente.replace(' ','_')}.docx", use_container_width=True)

        st.markdown("**5. Bitácora Hiper-Resumida (Copia y pega en SCOTT CRM):**")
        st.text_area("Reporte listo para SCOTT:", value=st.session_state.ai_log, height=90, key=f"scott_{canal_actual}")
        
        if st.button("Inyectar al Forecast del SAIV", key=f"iny_{canal_actual}"):
            f_hoy = datetime.now().strftime("%Y-%m-%d")
            div = "USD" if st.session_state.ai_usd > 0 else "MXN"
            mto = st.session_state.ai_usd if div == "USD" else st.session_state.ai_mxn
            q_ins = "INSERT INTO reportes (folio_proyecto, cliente, pain, monto, probabilidad, semana, divisa, siguiente_paso, fecha_prox, estatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            run_query(q_ins, (st.session_state.ai_folio, st.session_state.ai_cliente, st.session_state.ai_log, mto, 50, "W1", div, canal_actual, f_hoy, "3. Negociación"), fetch=False)
            st.success("Proyecto registrado en el Forecast.")

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
        
        headers = [str(x).upper().replace('\ufeff', '').strip() for x in df_raw.iloc
