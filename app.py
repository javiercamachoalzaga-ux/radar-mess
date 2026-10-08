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
st.set_page_config(
    page_title="SAIV | Radar Comercial MESS", 
    page_icon="logo mess 1.jpg", 
    layout="wide", 
    initial_sidebar_state="expanded"
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
    
    .alerta-estancado { background: #fff1f2; border-left: 5px solid #e11d48; padding: 15px; border-radius: 6px; margin-bottom: 10px; }
    .stButton>button { font-weight: 600; border-radius: 6px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    
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
    st.info("👈 **ATENCIÓN MÓVIL:** Toca el menú (rayitas) en la esquina superior izquierda de tu pantalla para ingresar la contraseña.")
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
            
        df_agrupado['Fase_Pipeline'] = df
