import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re
import io
import urllib.parse
from datetime import datetime
import google.generativeai as genai

try:
    from docx import Document
    docx_ok = True
except ImportError:
    docx_ok = False

st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide")

ia_activa = False
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    ia_activa = True

# Modelo compatible forzado de forma explícita y directa
def obtener_modelo_activo():
    return genai.GenerativeModel("gemini-2.0-flash")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .header-mess { background: linear-gradient(135deg, #003a70 0%, #002244 100%); padding: 22px 28px; border-radius: 10px; color: white; margin-bottom: 20px; border-left: 6px solid #ff6600; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .header-mess h1 { font-size: 26px; font-weight: 900; margin: 0; text-transform: uppercase; }
    .header-mess p { font-size: 13px; margin: 4px 0 0 0; color: #cbd5e1; text-transform: uppercase; font-weight: 600; letter-spacing: 1px; }
    div[data-testid="metric-container"] { background: #fff; border: 1px solid #e2e8f0; padding: 14px; border-radius: 8px; border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
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

st.markdown('<div class="header-mess"><h1>MESS Servicios Metrológicos</h1><p>SAIV | Sistema Automatizado de Ingeniería de Ventas & Copiloto KAM</p></div>', unsafe_allow_html=True)

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
        work['Proyecto'] = get_col(['PROYECTO', 'FOLIO'])
        work['Cotizacion'] = get_col(['COTIZACION', 'COTIZACIÓN', 'NO. COTIZACION', 'FOLIO COTIZACION'])
        work['Cliente'] = get_col(['CLIENTE', 'EMPRESA'])
        work['Area'] = get_col(['AREA', 'ÁREA'])
        work['Etapa'] = get_col(['ETAPA', 'FASE'])
        work['Desc'] = get_col(['DESCRIPCION'])
        work['Fecha_Creacion'] = get_col(['FECHA DE REGISTRO', 'FECHA CREACION', 'FECHA'])
        work['Fecha_Cierre'] = get_col(['FECHA DE CIERRE', 'CIERRE'])
        
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
                    
        work['USD'], work['MXN'] = m_usd, m_mxn
        work = work.dropna(subset=['Proyecto']).reset_index(drop=True)
        
        def fix_text(x):
            if pd.isna(x): return ""
            t = str(x)
            rep = {'ci?n':'ción','CI?N':'CIÓN','se?o':'seño','SE?O':'SEÑO','Dise?o':'Diseño','DISE?O':'DISEÑO','Diseóo':'Diseño','diseóo':'diseño','a?o':'año','A?O':'AÑO','metr?a':'metría','METR?A':'METRÍA','?tico':'ótico','?TICO':'ÓTICO','?tica':'ótica','?TICA':'ÓTICA','Â':'','Ã³':'ó','Ã¡':'á','Ã©':'é','Ã­':'í','Ãº':'ú'}
            for k, v in rep.items(): t = t.replace(k, v)
            t = re.sub(r'(?<=[a-zA-Z])\?(?=[a-zA-Z])', 'ó', t)
            return re.sub(r'\b\?+', 'S', t).strip()

        work['Cliente'] = work['Cliente'].apply(lambda x: re.sub(r'\s+', ' ', fix_text(x)).title())
        work['Cotizacion'] = work['Cotizacion'].apply(fix_text)
        work['Desc'] = work['Desc'].apply(fix_text)
        work['Area'] = work['Area'].apply(fix_text)
        
        work['Cliente'] = work.groupby('Proyecto')['Cliente'].transform(lambda x: x.ffill().bfill())
        work['Cotizacion'] = work.groupby('Proyecto')['Cotizacion'].transform(lambda x: x.ffill().bfill())
        
        dt_crea = pd.to_datetime(work['Fecha_Creacion'], errors='coerce', dayfirst=True)
        work['Dias_Activo'] = (pd.Timestamp.now() - dt_crea).dt.days.fillna(0).astype(int)
        
        df_g = work.groupby('Proyecto').agg({
            'Cotizacion': 'first', 'Cliente': 'first', 'Area': 'first', 'Etapa': 'first',
            'Desc': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip()!='']),
            'Dias_Activo': 'max', 'Fecha_Cierre': 'first', 'USD': 'sum', 'MXN': 'sum'
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
    except Exception:
        return pd.DataFrame()

archivo = st.sidebar.file_uploader("Subir extracción CSV de SCOTT", type=["csv"])
df = pd.DataFrame()
if archivo:
    df = procesar_csv(archivo.getvalue())
    if df.empty:
        st.sidebar.error("Error al leer formato SCOTT.")
    else:
        st.sidebar.divider()
        st.sidebar.markdown("**Motor de Búsqueda KAM (Sniper)**")
        tc = st.sidebar.number_input("Tipo de Cambio (MXN a USD)", value=18.0, step=0.5)
        df['Total_USD_Eq'] = df['USD'] + (df['MXN'] / tc)

        f_txt = st.sidebar.text_input("Buscar (Cliente, Proyecto, Cotización, Marca):")
        f_frescos = st.sidebar.checkbox("Ver Solo Proyectos En Tiempo (< 25 días)")
        f_rezagados = st.sidebar.checkbox("Ver Solo Proyectos Rezagados (>= 25 días)")
        f_min_usd = st.sidebar.number_input("Monto Mínimo (USD Eq):", min_value=0, value=0, step=5000)
        f_fase = st.sidebar.multiselect("Salud del Embudo:", sorted(df['Fase'].unique()))
        f_area = st.sidebar.multiselect("Área de Negocio:", sorted(df['Area'].unique()))
        f_pilar = st.sidebar.multiselect("Pilar Estratégico:", df['Pilar'].unique())
        
        if f_txt:
            df = df[df['Cliente'].str.contains(f_txt, case=False, na=False) | df['Proyecto'].astype(str).str.contains(f_txt, case=False, na=False) | df['Cotizacion'].astype(str).str.contains(f_txt, case=False, na=False) | df['Desc'].str.contains(f_txt, case=False, na=False)]
        if f_min_usd > 0: df = df[df['Total_USD_Eq'] >= f_min_usd]
        if f_fase: df = df[df['Fase'].isin(f_fase)]
        if f_area: df = df[df['Area'].isin(f_area)]
        if f_pilar: df = df[df['Pilar'].isin(f_pilar)]
        if f_frescos: df = df[df['Dias_Activo'] < 25]
        if f_rezagados: df = df[df['Dias_Activo'] >= 25]

t_dash, t_ia = st.tabs(["1. Visualización del Pipeline (Dashboards)", "2. Laboratorio IA (Estrategias)"])

with t_dash:
    if not df.empty:
        META_USD = 80000.0
        activos = df[df['Fase'].isin(['3. Negociación', '4. Esperando PO'])]
        usd_activo = activos['Total_USD_Eq'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Meta Mensual (USD)", f"${META_USD:,.0f}")
        c2.metric("Pipeline Filtrado Probable (USD Eq)", f"${usd_activo:,.0f}")
        c3.metric("Brecha para Meta (GAP)", f"${max(0, META_USD - usd_activo):,.0f}")
        st.divider()
        
        vista = st.radio("Selecciona la vista operativa:", ["Vista Global (USD Equivalente)", "Solo Proyectos en USD", "Solo Proyectos en MXN"], horizontal=True)
        if "USD Equivalente" in vista: df_graf, col_v = df.copy(), "Total_USD_Eq"
        elif "USD" in vista: df_graf, col_v = df[df['USD'] > 0].copy(), "USD"
        else: df_graf, col_v = df[df['MXN'] > 0].copy(), "MXN"
            
        st.markdown(f"#### Análisis Pareto 80/20 - {vista}")
        pareto = df_graf.groupby('Cliente')[col_v].sum().sort_values(ascending=False).reset_index()
        pareto = pareto[pareto[col_v] > 0]
        if not pareto.empty:
            pareto['Acumulado'] = pareto[col_v].cumsum() / pareto[col_v].sum()
            b = alt.Chart(pareto).mark_bar(color='#003a70').encode(x=alt.X('Cliente', sort=None), y=col_v)
            l = alt.Chart(pareto).mark_line(color='#ff6600', point=True).encode(x=alt.X('Cliente', sort=None), y=alt.Y('Acumulado', axis=alt.Axis(format='%')))
            st.altair_chart(alt.layer(b, l).resolve_scale(y='independent').properties(height=320), use_container_width=True)
            
        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown(f"**Forecast por Área ({col_v})**")
            df_a = df_graf.groupby('Area')[col_v].sum().reset_index()
            if not df_a.empty and df_a[col_v].sum() > 0:
                st.altair_chart(alt.Chart(df_a).mark_bar(color='#003a70').encode(x=col_v, y=alt.Y('Area', sort='-x')).properties(height=280), use_container_width=True)
        with cg2:
            st.markdown(f"**Salud del Embudo ({col_v})**")
            df_f = df_graf.groupby('Fase')[col_v].sum().reset_index()
            if not df_f.empty and df_f[col_v].sum() > 0:
                st.altair_chart(alt.Chart(df_f).mark_bar(color='#10b981').encode(x=col_v, y=alt.Y('Fase', sort='-x')).properties(height=280), use_container_width=True)

        st.divider()
        st.markdown(f"#### Detalle Operativo del Pipeline Activo - {vista}")
        cols_op = ['Proyecto', 'Cotizacion', 'Cliente', 'Desc', 'Dias_Activo', 'Fecha_Cierre', 'Fase', 'USD', 'MXN']
        df_disp = activos[cols_op].copy()
        if "USD Equivalente" not in vista:
            df_disp = df_disp[df_disp['MXN'] > 0] if "MXN" in vista else df_disp[df_disp['USD'] > 0]
            
        cnt = df_disp['Cliente'].value_counts()
        df_m = df_disp[df_disp['Cliente'].isin(cnt[cnt > 1].index)].copy()
        df_s = df_disp[df_disp['Cliente'].isin(cnt[cnt == 1].index)].copy()
        
        for dt in [df_m, df_s]:
            if not dt.empty:
                dt['USD'] = dt['USD'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")
                dt['MXN'] = dt['MXN'].apply(lambda x: f"${x:,.2f}" if x > 0 else "$0.00")

        ct1, ct2 = st.columns(2)
        with ct1:
            st.markdown("##### Venta Consultiva KAM (2+ Proyectos)")
            if not df_m.empty: st.dataframe(df_m.sort_values(by=['Cliente', 'Proyecto']), use_container_width=True, hide_index=True)
            else: st.info("Sin cuentas multiproducto bajo estos filtros.")
        with ct2:
            st.markdown("##### Venta Transaccional (1 Proyecto)")
            if not df_s.empty: st.dataframe(df_s.sort_values(by='Cliente'), use_container_width=True, hide_index=True)
            else: st.info("Sin cuentas individuales bajo estos filtros.")
    else:
        st.info("Sube el CSV de SCOTT o ajusta los filtros.")

with t_ia:
    st.markdown("### Laboratorio IA | Copiloto Estratégico KAM")
    if not df.empty:
        c_sel = st.selectbox("1. Selecciona Cliente:", ["--"] + sorted(df['Cliente'].unique()))
        if c_sel != "--":
            df_c = df[df['Cliente'] == c_sel]
            opc = df_c.apply(lambda x: f"Proj: [{x['Proyecto']}] | Cot: [{x['Cotizacion']}] | {str(x['Desc'])[:28]}... (${x['USD']:,.0f} USD / ${x['MXN']:,.0f} MXN) - {x['Dias_Activo']}d", axis=1).tolist()
            p_sel = st.multiselect("2. Folios a incluir (Bundle):", opc, default=opc[:1])
            
            if p_sel:
                ids = [re.search(r'Proj: \[(.*?)\]', o).group(1) for o in p_sel]
                cots = [re.search(r'Cot: \[(.*?)\]', o).group(1) for o in p_sel]
                df_sub = df[df['Proyecto'].isin(ids)]
                
                t_usd, t_mxn = df_sub['USD'].sum(), df_sub['MXN'].sum()
                eqs = " | ".join(df_sub['Desc'].tolist())
                cots_str = ", ".join([c for c in cots if c and str(c).strip() != ''])
                
                desglose_items = "\n".join([
                    f"• Cotización {r['Cotizacion']} (Proyecto {r['Proyecto']}): {r['Desc']} -> Inversión: ${r['USD']:,.2f} USD / ${r['MXN']:,.2f} MXN"
                    for _, r in df_sub.iterrows()
                ])
                
                st.markdown(f"""
                <div style="background-color:#f1f5f9; padding:15px; border-radius:8px; border-left:4px solid #003a70; margin-bottom:15px;">
                    <b>Valor del Paquete:</b> <span style='color:#003a70; font-weight:bold; font-size:18px;'>${t_usd:,.2f} USD</span> | <span style='color:#003a70; font-weight:bold;'>${t_mxn:,.2f} MXN</span><br>
                    <b>Cotizaciones:</b> {cots_str if cots_str else 'N/D'}<br>
                    <b>Alcance:</b> {eqs}
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    canal = st.radio("Canal de Comunicación:", ["Mensaje WhatsApp", "Correo Ejecutivo", "Llamada", "Visita Presencial"])
                    perfil = st.selectbox("Perfil del Interlocutor:", ["Ingeniero/Planta", "Comprador", "Director/Dueño"])
                with c2:
                    giro = st.text_input("Giro Industrial (Ej. Automotriz, Aeroespacial):")
                    ctx = st.text_area("Contexto Específico:", placeholder="Ej. Urge cerrar antes de fin de mes para asegurar calendario de calibración.")
                
                if ia_activa and st.button("Generar Estrategia de Cierre KAM", type="primary"):
                    with st.spinner("Ejecutando ingeniería de ventas (MEDDPICC, SPIN & Sandler)..."):
                        try:
                            prompt = f"""
                            Eres KAM senior en MESS Servicios Metrológicos (experto en metrología dimensional, calibración acreditada ISO/IEC 17025 y alta gama: Zeiss, Taylor Hobson, Wilson, Kreon).
                            Cliente: {c_sel} | Giro: {giro} | Interlocutor: {perfil} | Canal: {canal} | Contexto: {ctx}
                            Total Paquete: ${t_usd:,.2f} USD / ${t_mxn:,.2f} MXN.
                            
                            PROPUESTAS A INCLUIR:
                            {desglose_items}
                            
                            REGLAS ESTRICTAS PARA EL BLOQUE <MESSAGE>:
                            1. PROHIBIDO usar tablas Markdown (NO uses barras '|' ni ':---') y PROHIBIDO usar asteriscos '**'. El texto se mostrará en una caja de texto plano.
                            2. Presenta cada cotización en una lista vertical limpia y muy bien espaciada (dejando una línea en blanco entre cada propuesta) con este formato exacto:
                            
                            • Cotización [Número] - [Equipo/Servicio]
                              Impacto en planta: [Beneficio técnico metrológico o cumplimiento normativo IATF/ISO]
                              Inversión: [Monto exacto en USD o MXN]
                            
                            3. Fusiona SPIN Selling, MEDDPICC y cierre negativo Sandler con tono natural, directo y ejecutivo.
                            
                            Devuelve ÚNICAMENTE estas 4 etiquetas XML:
                            <ANALYSIS>...</ANALYSIS>
                            <MESSAGE>...</MESSAGE>
                            <OBJECTIONS>...</OBJECTIONS>
                            <LOG>...</LOG>
                            """
                            modelo_ia = obtener_modelo_activo()
                            res = modelo_ia.generate_content(prompt).text
                            
                            def ext(tag):
                                m = re.search(fr'<{tag}>(.*?)</{tag}>', res, re.DOTALL | re.IGNORECASE)
                                return m.group(1).strip() if m else ""
                            
                            msg_clean = re.sub(r'\|.*\|', '', ext('MESSAGE')).replace('**', '').strip()
                            
                            st.session_state['ia_res'] = {
                                'analisis': ext('ANALYSIS'), 'mensaje': msg_clean,
                                'objeciones': ext('OBJECTIONS'), 'log': ext('LOG')
                            }
                        except Exception as e:
                            st.error(f"Error IA: {e}")

                res_ia = st.session_state.get('ia_res', {})
                if res_ia.get('mensaje'):
                    st.divider()
                    st.info(f"**Análisis Estratégico (MEDDPICC & Sandler):**\n\n{res_ia['analisis']}")
                    st.markdown("#### Guion / Mensaje Táctico (Texto Limpio y Editable)")
                    msg_ed = st.text_area("Edita antes de enviar:", value=res_ia['mensaje'], height=280)
                    
                    wa_url = f"https://wa.me/?text={urllib.parse.quote(msg_ed)}"
                    st.markdown(f'<a href="{wa_url}" target="_blank" style="background-color:#25D366;color:white;padding:10px 18px;border-radius:5px;text-decoration:none;font-weight:bold;display:inline-block;">Enviar por WhatsApp Directo</a>', unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.warning(f"**Manejo Preventivo de Objeciones:**\n\n{res_ia['objeciones']}")
                    st.success(f"**Bitácora Sugerida para SCOTT:**\n\n{res_ia['log']}")
                    
                    if docx_ok:
                        def get_docx():
                            d = Document()
                            d.add_heading("ESTRATEGIA KAM - MESS", 0)
                            d.add_paragraph(f"Cliente: {c_sel}\nCotizaciones: {cots_str}\n\nANÁLISIS:\n{res_ia['analisis']}\n\nMENSAJE:\n{msg_ed}\n\nOBJECIONES:\n{res_ia['objeciones']}\n\nBITÁCORA SCOTT:\n{res_ia['log']}")
                            b = io.BytesIO()
                            d.save(b)
                            b.seek(0)
                            return b
                        st.download_button("Descargar Ficha Estratégica (.docx)", data=get_docx(), file_name=f"Estrategia_{c_sel}.docx")
    else:
        st.info("Sube tus datos para iniciar el Laboratorio IA.")
# FIN DEL SCRIPT SAIV
