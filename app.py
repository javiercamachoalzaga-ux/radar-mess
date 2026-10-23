import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re
import io
import urllib.parse
from datetime import datetime, date, time, timedelta
import google.generativeai as genai

try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide")

if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    ia_activa = True
else:
    ia_activa = False

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo { font-size: 34px; font-weight: 900; color: #003a70; text-transform: uppercase; margin-bottom: 0; }
    div[data-testid="metric-container"] { background: #fff; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .caja-ia { background: #f8fafc; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; margin-bottom: 15px; border: 1px solid #e2e8f0;}
    </style>
    """, unsafe_allow_html=True)

if not st.session_state.get("auth_ok"):
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña", type="password")
    if pwd == st.secrets.get("mi_contrasena", ""):
        st.session_state["auth_ok"] = True
        st.rerun()
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

st.markdown('<div class="titulo">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
st.caption("Dashboard Ejecutivo & Copiloto KAM | MESS Servicios Metrológicos")

@st.cache_data
def procesar_csv(file_bytes):
    try:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding='utf-8-sig', engine='python', header=None)
        except:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding='latin-1', engine='python', header=None)
            
        h_idx = -1
        for i, row in df.iterrows():
            if 'PROYECTO' in str(row.values).upper() and 'CLIENTE' in str(row.values).upper():
                h_idx = i
                break
        if h_idx == -1: return pd.DataFrame()
        
        headers = [str(x).upper().strip() for x in df.iloc[h_idx]]
        d = df.iloc[h_idx+1:].copy()
        d.columns = headers[:len(d.columns)]
        
        def get_col(keys):
            for k in keys:
                for c in d.columns:
                    if k in str(c).upper(): return d[c].copy()
            return pd.Series([None]*len(d))
            
        work = pd.DataFrame()
        work['ID'] = get_col(['PROYECTO', 'FOLIO'])
        work['Cliente'] = get_col(['CLIENTE', 'EMPRESA'])
        work['Area'] = get_col(['AREA', 'ÁREA'])
        work['Etapa'] = get_col(['ETAPA', 'FASE'])
        work['Desc'] = get_col(['DESCRIPCION'])
        
        m_usd, m_mxn = np.zeros(len(d)), np.zeros(len(d))
        c_mon = get_col(['MONEDA', 'DIVISA'])
        
        for c in d.columns:
            cn = str(c).upper()
            if any(k in cn for k in ['VALOR', 'MONTO', 'TOTAL', 'IMPORTE']):
                is_usd = 'USD' in cn
                for i in range(len(d)):
                    v_str = str(d[c].iloc[i]).upper()
                    m = re.search(r'-?\d+(?:\.\d+)?', v_str.replace(',','').replace('USD','').replace('MXN','').replace('$',''))
                    val = float(m.group()) if m else 0.0
                    mon = str(c_mon.iloc[i]).upper() if not c_mon.empty else ""
                    if is_usd or 'USD' in v_str or 'USD' in mon: m_usd[i] += val
                    else: m_mxn[i] += val
                    
        work['USD'] = m_usd
        work['MXN'] = m_mxn
        work = work.dropna(subset=['ID']).reset_index(drop=True)
        
        work['Cliente'] = work['Cliente'].apply(lambda x: re.sub(r'\s+', ' ', str(x).replace('?','ó')).strip().title())
        work['Desc'] = work['Desc'].apply(lambda x: str(x).replace('?','ó') if pd.notna(x) else "")
        work['Area'] = work['Area'].apply(lambda x: str(x).replace('?','ó') if pd.notna(x) else "")
        
        work['Cliente'] = work.groupby('ID')['Cliente'].transform(lambda x: x.ffill().bfill())
        
        df_g = work.groupby('ID').agg({
            'Cliente': 'first', 'Area': 'first', 'Etapa': 'first',
            'Desc': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip()!='']),
            'USD': 'sum', 'MXN': 'sum'
        }).reset_index()
        
        df_g = df_g[(df_g['USD']>0) | (df_g['MXN']>0)]
        df_g = df_g[df_g['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)]
        
        def set_pilar(r):
            t = str(r['Area'] + " " + r['Desc']).upper()
            if any(k in t for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama"
            if any(k in t for k in ["CALIBRACIÓN", "LABORATORIO", "DIMENSIONAL"]): return "2. Calibraciones"
            return "3. Productos Generales"
            
        def set_fase(e):
            e = str(e).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            if 'NEGOCIACI' in e: return "3. Negociación"
            if 'COTIZACI' in e: return "2. Cotización"
            return "1. Propuesta"
            
        df_g['Pilar'] = df_g.apply(set_pilar, axis=1)
        df_g['Fase'] = df_g['Etapa'].apply(set_fase)
        return df_g
    except Exception as e:
        return pd.DataFrame()

archivo = st.sidebar.file_uploader("Subir CSV de SCOTT", type=["csv"])
df = pd.DataFrame()
if archivo:
    df = procesar_csv(archivo.getvalue())
    if df.empty:
        st.sidebar.error("Error al leer formato SCOTT.")
    else:
        st.sidebar.divider()
        st.sidebar.markdown("**Filtros Rápidos**")
        f_pilar = st.sidebar.multiselect("Pilar", df['Pilar'].unique(), default=df['Pilar'].unique())
        f_txt = st.sidebar.text_input("Buscar Cliente/Folio")
        if f_pilar: df = df[df['Pilar'].isin(f_pilar)]
        if f_txt: df = df[df['Cliente'].str.contains(f_txt, case=False) | df['ID'].astype(str).str.contains(f_txt, case=False)]

t_dash, t_ia = st.tabs(["📊 1. Visualización del Pipeline (Dashboards)", "🧠 2. Laboratorio IA (Estrategias)"])

with t_dash:
    if not df.empty:
        META_USD = 80000.0
        tc = st.sidebar.number_input("Tipo de Cambio (MXN a USD)", value=18.0, step=0.5)
        
        df['Total_USD_Eq'] = df['USD'] + (df['MXN'] / tc)
        activos = df[df['Fase'].isin(['3. Negociación', '4. Esperando PO'])]
        
        # KPI Globales siempre en USD para monitoreo de Cuota
        usd_activo = activos['Total_USD_Eq'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Meta Mensual (USD)", f"${META_USD:,.0f}")
        c2.metric("Pipeline Probable (USD Eq)", f"${usd_activo:,.0f}")
        c3.metric("Brecha para Meta (GAP)", f"${max(0, META_USD - usd_activo):,.0f}")
        
        st.divider()
        
        # Botones de visualización
        vista = st.radio("📊 Selecciona la vista operativa de los gráficos y tablas:", ["Vista Global (USD Equivalente)", "Solo Proyectos en USD", "Solo Proyectos en MXN"], horizontal=True)
        
        if "USD Equivalente" in vista:
            df_graf = df.copy()
            col_valor = "Total_USD_Eq"
        elif "USD" in vista:
            df_graf = df[df['USD'] > 0].copy()
            col_valor = "USD"
        else:
            df_graf = df[df['MXN'] > 0].copy()
            col_valor = "MXN"
            
        st.markdown(f"#### Análisis Pareto 80/20 - {vista}")
        pareto = df_graf.groupby('Cliente')[col_valor].sum().sort_values(ascending=False).reset_index()
        pareto = pareto[pareto[col_valor] > 0]
        pareto['Acumulado'] = pareto[col_valor].cumsum() / pareto[col_valor].sum()
        
        if not pareto.empty:
            barras = alt.Chart(pareto).mark_bar(color='#34495e').encode(x=alt.X('Cliente', sort=None), y=col_valor)
            linea = alt.Chart(pareto).mark_line(color='#e74c3c', point=True).encode(x=alt.X('Cliente', sort=None), y=alt.Y('Acumulado', axis=alt.Axis(format='%')))
            st.altair_chart(alt.layer(barras, linea).resolve_scale(y='independent').properties(height=350), use_container_width=True)
        else:
            st.info(f"No hay proyectos activos en esta moneda para graficar el Pareto.")
            
        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown(f"**Forecast por Área ({col_valor})**")
            df_a = df_graf.groupby('Area')[col_valor].sum().reset_index()
            if not df_a.empty and df_a[col_valor].sum() > 0:
                st.altair_chart(alt.Chart(df_a).mark_bar(color='#003a70').encode(x=col_valor, y=alt.Y('Area', sort='-x')).properties(height=300), use_container_width=True)
        with cg2:
            st.markdown(f"**Salud del Embudo ({col_valor})**")
            df_f = df_graf.groupby('Fase')[col_valor].sum().reset_index()
            if not df_f.empty and df_f[col_valor].sum() > 0:
                st.altair_chart(alt.Chart(df_f).mark_bar(color='#2ecc71').encode(x=col_valor, y=alt.Y('Fase', sort='-x')).properties(height=300), use_container_width=True)

        st.divider()
        st.markdown(f"#### Detalle Operativo del Pipeline Activo - {vista}")
        df_display = activos[['ID', 'Cliente', 'Desc', 'Fase', 'USD', 'MXN']].copy()
        
        # Filtramos la tabla operativa según el botón seleccionado
        if "USD Equivalente" not in vista:
            if "MXN" in vista: df_display = df_display[df_display['MXN'] > 0]
            else: df_display = df_display[df_display['USD'] > 0]
            
        df_display['USD'] = df_display['USD'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")
        df_display['MXN'] = df_display['MXN'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        st.info("Sube el CSV de SCOTT para visualizar tu Pipeline.")

with t_ia:
    st.markdown("### Generador de Estrategias y Guiones (KAM)")
    if not df.empty:
        c_sel = st.selectbox("1. Selecciona Cliente:", ["--"] + sorted(df['Cliente'].unique()))
        if c_sel != "--":
            df_c = df[df['Cliente'] == c_sel]
            opc = df_c.apply(lambda x: f"[{x['ID']}] {str(x['Desc'])[:40]}... (${x['USD']:,.0f} USD / ${x['MXN']:,.0f} MXN)", axis=1).tolist()
            p_sel = st.multiselect("2. Folios a incluir (Bundle):", opc, default=opc[:1])
            
            if p_sel:
                ids = [o.split("]")[0].replace("[", "") for o in p_sel]
                df_s = df[df['ID'].isin(ids)]
                
                t_usd, t_mxn = df_s['USD'].sum(), df_s['MXN'].sum()
                eqs = " | ".join(df_s['Desc'].tolist())
                
                st.markdown(f"**Valor del Paquete:** <span style='color:#27ae60;font-size:18px;'>${t_usd:,.2f} USD</span> | ${t_mxn:,.2f} MXN", unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    canal = st.radio("Canal:", ["Mensaje WhatsApp", "Correo Ejecutivo", "Llamada", "Visita Presencial"])
                    perfil = st.selectbox("Interlocutor:", ["Ingeniero/Planta", "Comprador", "Director/Dueño"])
                with c2:
                    giro = st.text_input("Giro (Ej. Aeroespacial):")
                    ctx = st.text_area("Contexto (Opcional):", placeholder="Ej. Tienen parado el proyecto por presupuesto.")
                
                if ia_activa and st.button("🧠 Generar Estrategia de Cierre", type="primary"):
                    with st.spinner("Fusionando MEDDPICC y Sandler..."):
                        try:
                            prompt = f"Cliente: {c_sel}. Perfil: {perfil}. Giro: {giro}. Equipos: {eqs}. Monto: ${t_usd} USD. Acción: {canal}. Contexto: {ctx}. Eres KAM de MESS B2B. Usa MEDDPICC, SPIN y Sandler (cierre negativo). Devuelve SOLO en XML: <ANALYSIS> <MESSAGE> <OBJECTIONS> <LOG>."
                            res = genai.GenerativeModel("gemini-pro").generate_content(prompt).text
                            
                            def ext(tag): 
                                m = re.search(fr'<{tag}>(.*?)</{tag}>', res, re.DOTALL)
                                return m.group(1).strip() if m else ""
                            
                            st.session_state['ia_res'] = {
                                'analisis': ext('ANALYSIS'), 'mensaje': ext('MESSAGE'),
                                'objeciones': ext('OBJECTIONS'), 'log': ext('LOG')
                            }
                        except Exception as e:
                            st.error(f"Error IA: {e}")

                res_ia = st.session_state.get('ia_res', {})
                if res_ia.get('mensaje'):
                    st.divider()
                    st.info(f"**Análisis Estratégico:**\n{res_ia['analisis']}")
                    
                    st.markdown("#### 💬 Guion / Mensaje (Editable)")
                    msg_editado = st.text_area("Ajusta el texto antes de enviarlo:", value=res_ia['mensaje'], height=150)
                    
                    wa_url = f"https://wa.me/?text={urllib.parse.quote(msg_editado)}"
                    st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:8px 15px;border-radius:5px;text-decoration:none;font-weight:bold;">📲 Enviar por WhatsApp</a>', unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.warning(f"**Manejo de Objeciones:**\n{res_ia['objeciones']}")
                    st.success(f"**Bitácora SCOTT:**\n{res_ia['log']}")
                    
                    if docx_disponible:
                        def get_docx():
                            d = Document()
                            d.add_heading("ESTRATEGIA KAM", 0)
                            d.add_paragraph(f"Cliente: {c_sel}\nAnálisis:\n{res_ia['analisis']}\n\nMensaje Final:\n{msg_editado}")
                            b = io.BytesIO()
                            d.save(b)
                            b.seek(0)
                            return b
                        st.download_button("Descargar Ficha .docx", data=get_docx(), file_name="Estrategia.docx")
    else:
        st.info("Sube tus datos para iniciar el Laboratorio IA.")
