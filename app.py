import streamlit as st
import pandas as pd
import numpy as np
import re
import altair as alt
import sqlite3
import google.generativeai as genai
import io
import urllib.parse
from datetime import datetime, timedelta

# Manejo de excepción para python-docx
try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO
# ==========================================
st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide", initial_sidebar_state="expanded")

# Inyección estricta de CSS Corporativo (Sin emojis en títulos nativos de ST, solo CSS)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.metric-card {
    background-color: #f8fafc;
    border-left: 5px solid #003a70;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    margin-bottom: 1rem;
}
.metric-title {
    font-size: 14px;
    font-weight: 600;
    color: #003a70;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 5px;
}
.metric-value {
    font-size: 28px;
    font-weight: 700;
    color: #2c3e50;
}
.header-title {
    color: #003a70;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SEGURIDAD Y AUTENTICACIÓN
# ==========================================
st.sidebar.markdown("<h2 style='color:#003a70;'>Acceso SAIV</h2>", unsafe_allow_html=True)
password = st.sidebar.text_input("Ingrese Credencial KAM", type="password")

try:
    EXPECTED_PASSWORD = st.secrets["mi_contrasena"]
    GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    st.error("Error: No se encontró el archivo de secretos (.streamlit/secrets.toml).")
    st.stop()

if password != EXPECTED_PASSWORD:
    st.sidebar.warning("Autenticación requerida.")
    st.stop()

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    st.sidebar.error("Falta API Key de Gemini.")

# ==========================================
# 3. BASE DE DATOS LOCAL (SQLite RevOps)
# ==========================================
def init_db():
    conn = sqlite3.connect('mess_radar.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS agenda
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, hora TEXT, cliente TEXT, estatus TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bitacora
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, folio TEXT, monto REAL, moneda TEXT, probabilidad REAL, semana TEXT, log TEXT, fecha_registro TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 4. MOTOR PANDAS (Lógica de Extracción)
# ==========================================
def clean_currency(value):
    if pd.isna(value): return 0.0
    val_str = str(value).upper()
    val_str = re.sub(r'[^\d.]', '', val_str)
    try:
        return float(val_str) if val_str else 0.0
    except ValueError:
        return 0.0

def detect_currency(value, col_name):
    combined = str(value).upper() + " " + str(col_name).upper()
    if 'USD' in combined: return 'USD'
    return 'MXN'

@st.cache_data(show_spinner=False)
def process_crm_file(file):
    try:
        content = file.read().decode('utf-8-sig', errors='replace').splitlines()
    except Exception:
        file.seek(0)
        content = file.read().decode('latin-1', errors='replace').splitlines()
    
    header_idx = -1
    for i, line in enumerate(content):
        if 'PROYECTO' in line.upper() and 'CLIENTE' in line.upper():
            header_idx = i
            break
    
    if header_idx == -1:
        st.error("No se encontraron las columnas clave (PROYECTO, CLIENTE).")
        return pd.DataFrame()
    
    file.seek(0)
    df = pd.read_csv(file, skiprows=header_idx, encoding='utf-8-sig' if 'utf-8' in file.name else 'latin-1')
    df.dropna(how='all', inplace=True)
    df.columns = [str(c).upper().strip() for c in df.columns]
    
    # Estandarización de columnas si existen
    if 'PROYECTO' in df.columns:
        df.rename(columns={'PROYECTO': 'ID_PROYECTO'}, inplace=True)
        
    # Limpieza Financiera
    monto_col = [c for c in df.columns if 'MONTO' in c or 'VALOR' in c or 'PRECIO' in c]
    if monto_col:
        col = monto_col[0]
        df['Moneda_Temp'] = df.apply(lambda row: detect_currency(row[col], col), axis=1)
        df['Monto_Limpio'] = df[col].apply(clean_currency)
        df['Monto_USD'] = np.where(df['Moneda_Temp'] == 'USD', df['Monto_Limpio'], df['Monto_Limpio'] / 18.0) # TC aprox
        df['Monto_MXN'] = np.where(df['Moneda_Temp'] == 'MXN', df['Monto_Limpio'], df['Monto_Limpio'] * 18.0)
    else:
        df['Monto_USD'] = 0.0
        df['Monto_MXN'] = 0.0

    # Clasificación de Pilar y Fase
    def classify_pillar(desc):
        desc = str(desc).lower()
        if any(x in desc for x in ['cmm', 'laser', 'brazo', 'alta gama']): return "1. Alta Gama"
        if any(x in desc for x in ['calibracion', 'servicio']): return "2. Calibraciones"
        return "3. Productos Generales"

    def classify_phase(etapa):
        etapa = str(etapa).lower()
        if 'ganado' in etapa or 'cierre' in etapa: return "5. Cerrado Ganado"
        if 'po' in etapa or 'orden' in etapa: return "4. Esperando PO"
        if 'negocia' in etapa: return "3. Negociación"
        if 'cotiza' in etapa: return "2. Cotización"
        return "1. Propuesta"
    
    desc_col = next((c for c in df.columns if 'DESC' in c or 'AREA' in c or 'TIPO' in c), 'CLIENTE')
    fase_col = next((c for c in df.columns if 'ETAPA' in c or 'FASE' in c or 'ESTATUS' in c), 'CLIENTE')
    
    df['Pilar_Estrategico'] = df[desc_col].apply(classify_pillar)
    df['Fase_Pipeline'] = df[fase_col].apply(classify_phase)
    
    # Simulación de días inactivos (si no hay fecha)
    if 'DIAS_INACTIVO' not in df.columns:
        np.random.seed(42)
        df['DIAS_INACTIVO'] = np.random.randint(0, 30, size=len(df))

    return df

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1 class='header-title'>SAIV | Radar Comercial MESS</h1>", unsafe_allow_html=True)
st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("Cargar Extracción CRM (CSV)", type=['csv'])

df = pd.DataFrame()
if uploaded_file is not None:
    df = process_crm_file(uploaded_file)

tab1, tab2, tab3, tab4 = st.tabs([
    "Dashboards CRM", 
    "Proyectos Estancados", 
    "Laboratorio Táctico IA", 
    "Gestión Comercial"
])

# ------------------------------------------
# TAB 1: DASHBOARDS CRM
# ------------------------------------------
with tab1:
    if df.empty:
        st.info("Cargue un archivo CSV en el menú lateral para visualizar los dashboards.")
    else:
        # KPIs
        meta_mensual_usd = 80000.0
        pipeline_activo = df[df['Fase_Pipeline'] != "5. Cerrado Ganado"]['Monto_USD'].sum()
        brecha = meta_mensual_usd - pipeline_activo
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Meta Mensual</div><div class='metric-value'>${meta_mensual_usd:,.2f} USD</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Pipeline Activo</div><div class='metric-value'>${pipeline_activo:,.2f} USD</div></div>", unsafe_allow_html=True)
        with c3:
            color = "#e74c3c" if brecha > 0 else "#27ae60"
            st.markdown(f"<div class='metric-card' style='border-left-color:{color};'><div class='metric-title'>Brecha (GAP)</div><div class='metric-value' style='color:{color};'>${brecha:,.2f} USD</div></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        # Pareto (80/20)
        st.markdown("<h3 style='color:#003a70;'>Pareto de Clientes (USD)</h3>", unsafe_allow_html=True)
        df_pareto = df.groupby('CLIENTE')['Monto_USD'].sum().reset_index().sort_values('Monto_USD', ascending=False)
        df_pareto['Cum_Pct'] = df_pareto['Monto_USD'].cumsum() / df_pareto['Monto_USD'].sum() * 100
        
        bar = alt.Chart(df_pareto).mark_bar(color='#2c3e50').encode(
            x=alt.X('CLIENTE', sort=None, title="Cliente"),
            y=alt.Y('Monto_USD', title="Monto USD")
        )
        line = alt.Chart(df_pareto).mark_line(color='#e74c3c', strokeWidth=3).encode(
            x=alt.X('CLIENTE', sort=None),
            y=alt.Y('Cum_Pct', title="% Acumulado")
        )
        st.altair_chart(alt.layer(bar, line).resolve_scale(y='independent').interactive(), use_container_width=True)
        
        col_charts1, col_charts2 = st.columns(2)
        with col_charts1:
            st.markdown("<h4 style='color:#003a70;'>Forecast por Pilar</h4>", unsafe_allow_html=True)
            df_pilar = df.groupby('Pilar_Estrategico')['Monto_USD'].sum().reset_index()
            c_pilar = alt.Chart(df_pilar).mark_bar().encode(
                x='Monto_USD', y=alt.Y('Pilar_Estrategico', sort='-x'), color=alt.value('#003a70')
            )
            st.altair_chart(c_pilar, use_container_width=True)
            
        with col_charts2:
            st.markdown("<h4 style='color:#003a70;'>Salud del Embudo</h4>", unsafe_allow_html=True)
            df_fase = df.groupby('Fase_Pipeline')['Monto_USD'].sum().reset_index()
            c_fase = alt.Chart(df_fase).mark_bar().encode(
                x='Monto_USD', y=alt.Y('Fase_Pipeline', sort='-x'), color=alt.value('#3498db')
            )
            st.altair_chart(c_fase, use_container_width=True)
            
        # Cross-Selling
        st.markdown("<h3 style='color:#003a70;'>Oportunidades de Cross-Selling</h3>", unsafe_allow_html=True)
        df_cross = df.pivot_table(index='CLIENTE', columns='Pilar_Estrategico', values='Monto_USD', aggfunc='sum').fillna(0)
        if '2. Calibraciones' in df_cross.columns and '1. Alta Gama' in df_cross.columns:
            target_clients = df_cross[(df_cross['2. Calibraciones'] > 0) & (df_cross['1. Alta Gama'] == 0)]
            if not target_clients.empty:
                st.dataframe(target_clients[['2. Calibraciones']], use_container_width=True)
            else:
                st.success("No se encontraron brechas de cross-selling de Calibraciones a Alta Gama.")

# ------------------------------------------
# TAB 2: PROYECTOS ESTANCADOS
# ------------------------------------------
with tab2:
    if not df.empty:
        st.markdown("<h3 style='color:#003a70;'>Proyectos en Riesgo (>15 Días Inactivos)</h3>", unsafe_allow_html=True)
        fases_iniciales = ["1. Propuesta", "2. Cotización", "3. Negociación"]
        df_estancados = df[(df['Fase_Pipeline'].isin(fases_iniciales)) & (df['DIAS_INACTIVO'] > 15)]
        
        if df_estancados.empty:
            st.success("¡Excelente! No tienes proyectos estancados.")
        else:
            for idx, row in df_estancados.iterrows():
                st.markdown(f"""
                <div style='background-color:#ffebee; padding:15px; border-left:5px solid #e53935; border-radius:5px; margin-bottom:10px;'>
                    <strong style='color:#b71c1c;'>{row.get('CLIENTE', 'Desconocido')}</strong> - {row.get('ID_PROYECTO', 'Sin Folio')} <br>
                    Monto: ${row.get('Monto_USD', 0):,.2f} USD | Días inactivo: {row.get('DIAS_INACTIVO', 0)}
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Generar Rescate (Sandler) para {row.get('ID_PROYECTO', idx)}", key=f"btn_{idx}"):
                    try:
                        model = genai.GenerativeModel('gemini-pro')
                        prompt = f"""
                        Actúa como un KAM B2B aplicando el "cierre negativo de Sandler".
                        Cliente: {row.get('CLIENTE')}
                        Proyecto: {row.get('ID_PROYECTO')}
                        Escribe un correo muy breve, profesional y directo sugiriendo que tal vez ya no es prioridad y si deberíamos cerrar el archivo.
                        """
                        response = model.generate_content(prompt)
                        st.text_area("Borrador Sugerido", response.text, height=150)
                    except Exception as e:
                        st.error(f"Error generando rescate: {e}")
    else:
        st.info("Cargue datos para evaluar estancamiento.")

# ------------------------------------------
# TAB 3: LABORATORIO TÁCTICO IA
# ------------------------------------------
with tab3:
    st.markdown("<h3 style='color:#003a70;'>Generador de Táctica RevOps</h3>", unsafe_allow_html=True)
    origen = st.radio("Origen de datos", ["CRM CSV", "Manual / Showroom"], horizontal=True)
    
    sel_cliente = ""
    sel_folios = ""
