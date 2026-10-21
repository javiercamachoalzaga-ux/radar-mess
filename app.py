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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, cliente TEXT, contacto TEXT,
            objetivo TEXT, estatus TEXT
        )
    """)
    
    cursor.execute("PRAGMA table_info(agenda)")
    columnas_agenda = [col[1] for col in cursor.fetchall()]
    if 'horario' not in columnas_agenda:
        cursor.execute("ALTER TABLE agenda ADD COLUMN horario TEXT DEFAULT '09:00'")
        
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_rep TEXT, cliente TEXT, resumen TEXT,
            pain TEXT, monto REAL, probabilidad INTEGER,
            semana TEXT, siguiente_paso TEXT, proxima_fecha TEXT,
            estatus TEXT
        )
    """)
    
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
# Variables puente para auto-llenado
if 'monto_usd_ia' not in st.session_state: st.session_state.monto_usd_ia = 0.0
if 'monto_mxn_ia' not in st.session_state: st.session_state.monto_mxn_ia = 0.0

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
