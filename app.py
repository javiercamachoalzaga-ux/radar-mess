import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import io
import sqlite3
import google.generativeai as genai

# Intento de importar docx
try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y UI/UX (CSS)
# ==========================================
# Se actualiza el page_icon al logo circular que ya tienes
st.set_page_config(page_title="SAIV | Radar Comercial MESS", page_icon="logo mess 1.jpg", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    
    /* Ocultar menú y footer por defecto */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Variables de color corporativo */
    :root { --mess-blue: #003a70; --mess-dark: #2c3e50; --mess-light: #f8fafc; }
    
    .titulo-radar { font-size: 36px; font-weight: 900; color: var(--mess-blue); margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #64748b; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid var(--mess-blue); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #64748b !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: var(--mess-dark) !important; }
    
    .alerta-estancado { background: #fff1f2; border-left: 5px solid #e11d48; padding: 15px; border-radius: 6px; margin-bottom: 10px; }
    .stButton>button { font-weight: 600; border-radius: 6px; }
    .ficha-scott { background-color: #f4f6f7; padding: 20px; border-radius: 8px; border: 1px solid #d5d8dc; margin-bottom: 20px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

# 1.1 Logo en la barra lateral superior (USANDO LOGO MESS 2.JPG)
st.sidebar.image("logo mess 2.jpg", use_container_width=True)

# ==========================================
# 2. SEGURIDAD: VERIFICACIÓN DE CONTRASEÑA
# ==========================================
def check_password():
    if "mi_contrasena" not in st.secrets: return True
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña corporativa", type="password")
    if pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña corporativa en el menú lateral para acceder al SAIV.")
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
# 4. BASE DE DATOS SQLITE (MIGRACIÓN AUTOMÁTICA)
# ==========================================
def init_db():
    conn = sqlite3.connect("mess_radar.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, horario TEXT, cliente TEXT, contacto TEXT,
            objetivo TEXT, estatus TEXT, notas_audio TEXT
        )
    """)
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
    
    cursor.execute("PRAGMA table_info(agenda)")
    columnas_agenda = [col[1] for col in cursor.fetchall()]
    if 'horario' not in columnas_agenda: cursor.execute("ALTER TABLE agenda ADD COLUMN horario TEXT DEFAULT '09:00'")
    if 'notas_audio' not in columnas_agenda: cursor.execute("ALTER TABLE agenda ADD COLUMN notas_audio TEXT")

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
# 5.
