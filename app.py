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

def init_
