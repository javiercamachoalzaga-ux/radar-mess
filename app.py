import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import io
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

# Variables de memoria para la IA
for var in ['tactica_analisis', 'tactica_mensaje', 'tactica_objeciones', 'tactica_marketing', 
            'tactica_bitacora', 'tactica_cliente', 'tactica_id', 'tactica_equipo', 'tactica_monto']:
    if var not in st.session_state: 
        st.session_state[var] = ""
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
st.markdown('<div class="subtitulo">Módulo CRM SCOTT | MESS</div>', unsafe_allow_html=True)

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
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE", "CIERRE", "FECHA CIERRE"])
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
            'Fecha_Cierre': 'first', 'Estatus': 'first', 'Etapa': 'first',
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
        st.sidebar.error(f
