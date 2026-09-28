import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re
import google.generativeai as genai
import urllib.parse
import io

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
# MEMORIA DE SESIÓN (STATE)
# ==========================================
if 'proyecto_foco' not in st.session_state: st.session_state.proyecto_foco = None
if 'tactica_analisis' not in st.session_state: st.session_state.tactica_analisis = ""
if 'tactica_whatsapp' not in st.session_state: st.session_state.tactica_whatsapp = ""
if 'tactica_correo' not in st.session_state: st.session_state.tactica_correo = ""
if 'tactica_llamada' not in st.session_state: st.session_state.tactica_llamada = ""
if 'tactica_marketing' not in st.session_state: st.session_state.tactica_marketing = ""
if 'tactica_bitacora' not in st.session_state: st.session_state.tactica_bitacora = ""
if 'tactica_cliente' not in st.session_state: st.session_state.tactica_cliente = ""
if 'tactica_id' not in st.session_state: st.session_state.tactica_id = ""
if 'tactica_equipo' not in st.session_state: st.session_state.tactica_equipo = ""
if 'tactica_monto' not in st.session_state: st.session_state.tactica_monto = ""

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

# ==========================================
# SIMULACIÓN DE DATOS MEDDPICC
# ==========================================
def generar_datos_meddpicc():
    data = {
        'Oportunidad': ['CMM Mitutoyo Crysta-Apex - Ford', 'Scantech SimScan - Fulltech', 'Brazo Faro / Servicios - Tremec', 'Calibración Dimensional Anual - Dana', 'Zeiss Contura (Competencia) - BRP'],
        'Valor_USD': [85000, 32842, 45000, 8500, 120000],
        'Etapa_Pipeline': [3, 4, 2, 5, 1],
        'M': [1, 2, 0, 2, 0], 'E': [2, 1, 1, 2, 0], 'D1': [1, 2, 1, 2, 1], 'D2': [1, 2, 0, 2, 0],
        'P': [2, 2, 1, 2, 1], 'I': [1, 1, 0, 2, 0], 'C1': [2, 2, 1, 2, 0], 'C2': [1, 2, 0, 2, 1]
    }
    df_m = pd.DataFrame(data)
    df_m['Health_Score'] = df_m[['M','E','D1','D2','P','I','C1','C2']].sum(axis=1)
    
    def asignar_estado(score):
        if score < 8: return 'Riesgo Alto'
        elif 8 <= score <= 12: return 'Precaución'
        else: return 'Saludable'
            
    df_m['Estado'] = df_m['Health_Score'].apply(asignar_estado)
    return df_m

df_meddpicc = generar_datos_meddpicc()

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
st.markdown('<div class="subtitulo">Módulo CRM SCOTT & Auditoría MEDDPICC | Revenue Operations</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])

if archivo_cargado is not None:
    try:
        # --- LECTOR ROBUSTO Y ALINEACIÓN DE ARCHIVOS SCOTT ---
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1', header=None, sep=None, engine='python')
        header_idx = -1
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.dropna()]).strip()
            if 'PROYECTO' in row_str and 'CLIENTE' in row_str:
                header_idx = idx
                break
                
        if header_idx == -1:
            st.error("No se detectó el formato del CRM. Asegúrate de subir la plantilla original de SCOTT.")
            st.stop()
            
        headers = [str(x).upper().replace('\ufeff', '').strip() for x in df_raw.iloc[header_idx] if pd.notna(x)]
        df_data = df_raw.iloc[header_idx+1:].copy()
        df_data = df_data.dropna(axis=1, how='all')
        
        if len(df_data.columns) >= len(headers):
            df_data = df_data.iloc[:, :len(headers)]
            df_data.columns = headers
        else:
            df_data.columns = headers[:len(df_data.columns)]
            
        if 'PROYECTO' in df_data.columns:
            df_data = df_data.dropna(subset=['PROYECTO']).reset_index(drop=True)
        else:
            st.error("Fallo de lectura en la columna PROYECTO.")
            st.stop()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_data.columns:
                    if str(col).upper().strip() == clave or str(col).upper().strip() == f"{clave}.1":
                        return df_data[col].copy()
            return pd.Series([None] * len(df_data))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Cotizacion'] = buscar_col(["COTIZACION"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def sanear_y_limpiar(texto):
            if pd.isna(texto): return ""
            t = str(texto)
            t = t.replace("?", "ó").replace("  ", " ")
            return re.sub(r'\s+', ' ', t).strip().title()

        for col in ['Cliente', 'Descripcion', 'Area', 'Estatus', 'Etapa']:
            df_clean[col] = df_clean[col].apply(sanear_y_limpiar)

        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        def extraer_numero(val_str):
            try: return float(''.join(c for c in str(val_str).upper() if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn, monto_usd = pd.Series([0.0]*len(df_data)), pd.Series([0.0]*len(df_data))
        for col in df_data.columns:
            if str(col).upper().strip().startswith("VALOR"):
                monto_mxn += df_data[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                monto_usd += df_data[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
        
        df_clean['Monto_MXN'], df_clean['Monto_USD'] = monto_mxn, monto_usd

        # AGRUPACIÓN POR PROYECTO
        df = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first',
            'Cotizacion': lambda x: ' / '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Area': 'first', 'Fecha_Creacion': 'first', 'Fecha_Cierre': 'first',
            'Estatus': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum', 'Monto_USD': 'sum'
        }).reset_index()

        df.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        
        df = df[(df['Monto_MXN'] > 0) | (df['Monto_USD'] > 0)]
        filtro_estatus = df['Estatus'].str.contains('PROCESO', case=False, na=False)
        filtro_etapa = df['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)
        df = df[filtro_estatus | filtro_etapa].copy()
        
        # CLASIFICACIÓN (PILARES Y MARCAS)
        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama (Servicios Especiales)"
            elif any(k in texto for k in ["CALIBRACIÓN", "CALIBRACION", "LABORATORIO", "DIMENSIONAL", "PRENSA"]): return "2. Calibraciones (Comunes)"
            else: return "3. Productos (Equipos y Consumibles)"
        
        def clasificar_marca(desc):
            texto = str(desc).upper()
            marcas = ["BATY", "MITUTOYO", "ZEISS", "FLUKE", "MAGTROL", "BUEHLER", "WILSON", "SCANTECH", "KREON", "TAYLOR HOBSON", "GALDABINI", "ANTON PAAR"]
            for marca in marcas:
                if marca in texto: return marca.title()
            return "Multimarca / No Especificada"
            
        df['Pilar_Estrategico'] = df.apply(clasificar_pilar, axis=1)
        df['Marca_Detectada'] = df['Descripcion'].apply(clasificar_marca)
        
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            else: return "5. En Proceso"
            
        df['Fase_Pipeline'] = df['Etapa'].apply(clasificar_fase)
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)
        df['Días_Activo'] = (pd.Timestamp.now() - df['Fecha_Creacion_DT']).dt.days

        # --- FILTROS GLOBALES ---
        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        opciones_pilares = df['Pilar_Estrategico'].unique().tolist()
        filtro_pilar = st.sidebar.multiselect("Filtrar por Pilar de Negocio:", opciones_pilares, default=opciones_pilares)
        busqueda_proyecto = st.sidebar.text_input("Buscar Folio o Cliente:")
        
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]
        if filtro_pilar:
            df = df[df['Pilar_Estrategico'].isin(filtro_pilar)]

        mes_actual, anio_actual = pd.Timestamp.now().month, pd.Timestamp.now().year
        
        # ==========================================
        # TABS DE NAVEGACIÓN
        # ==========================================
        tab_dashboards, tab_enablement, tab_scott, tab_meddpicc = st.tabs([
            "1. Dashboards CRM", 
            "2. Proyectos Estancados", 
            "3. Laboratorio IA (360°)",
            "4. Dashboard MEDDPICC"
        ])

        # ==========================================
        # TAB 1: DASHBOARDS DIRECTIVOS (RESTAURADOS AL 100%)
        # ==========================================
        with tab_dashboards:
            st.markdown("### Análisis de Forecast vs Cuota ($80K USD)")
            META_MENSUAL_USD = 80000.00
            
            df_mes = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)]
            usd_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_USD'].sum()
            mxn_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_MXN'].sum()
            
            gap_actual_usd = META_MENSUAL_USD - usd_caliente
            
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("Meta Comercial Mensual", f"${META_MENSUAL_USD:,.2f} USD")
            col_g2.metric("Pipeline Probable (USD)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN extra")
            if gap_actual_usd > 0:
                col_g3.metric("GAP (Brecha para Meta)", f"${gap_actual_usd:,.2f} USD", "- Acción requerida")
            else:
                col_g3.metric("GAP (Brecha)", "$0.00 USD", "+ Meta Cubierta")
            
            st.divider()
            
            col_sel1, col_sel2 = st.columns([1, 3])
            with col_sel1:
                moneda_sel = st.selectbox("Seleccionar Moneda para Gráficos:", ["USD ($)", "MXN ($)"])
            
            col_val = 'Monto_USD' if moneda_sel == "USD ($)" else 'Monto_MXN'
            simbolo_moneda = '$,.2f'
            
            st.divider()
            
            if df.empty:
                st.warning("No hay datos para graficar con los filtros actuales.")
            else:
                st.markdown(f"#### Análisis Pareto 80/20 por Cuentas Clave ({moneda_sel})")
                st.caption("Visualiza qué clientes concentran el grueso de tu pipeline.")
                
                df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
                df_pareto = df_pareto[df_pareto[col_val] > 0]
                df_pareto = df_pareto.sort_values(by=col_val, ascending=False).reset_index(drop=True)
                
                if not df_pareto.empty:
                    df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
                    df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
                    
                    barras_pareto = alt.Chart(df_pareto).mark_bar(color='#34495e').encode(
                        x=alt.X('Cliente', sort=None, title='Cliente (Ordenados por Monto)', axis=alt.Axis(labelLimit=0)),
                        y=alt.Y(col_val, title=f'Valor {moneda_sel}'),
                        tooltip=['Cliente', alt.Tooltip(col_val, format=simbolo_moneda), alt.Tooltip('Porcentaje', format='.1%')]
                    )
                    
                    linea_pareto = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(
                        x=alt.X('Cliente', sort=None),
                        y=alt.Y('Acumulado', title='Porcentaje Acumulado', axis=alt.Axis(format='%')),
                        tooltip=['Cliente', alt.Tooltip('Acumulado', format='.1%')]
                    )
                    
                    grafico_pareto = alt.layer(barras_pareto, linea_pareto).resolve_scale(
                        y='independent'
                    ).properties(height=450)
                    
                    st.altair_chart(grafico_pareto, use_container_width=True)
                    
                    top_20_percent_clientes = df_pareto[df_pareto['Acumulado'] <= 0.8]
                    if not top_20_percent_clientes.empty:
                        num_clientes = len(top_20_percent_clientes)
                        st.info(f"💡 **Insight Estratégico:** Solo **{num_clientes} cliente(s)** conforman aproximadamente el 80% del valor total de tu pipeline actual.")
                
                st.divider()

                col_g1, col_g2 = st.columns(2)
                
                with col_g1:
                    st.markdown(f"**Forecast por Área Oficial ({moneda_sel})**")
                    df_areas = df.groupby('Area')[col_val].sum().reset_index()
                    df_areas = df_areas[df_areas[col_val] > 0] 
                    if not df_areas.empty:
                        grafico_areas = alt.Chart(df_areas).mark_bar(color='#003a70').encode(
                            x=alt.X(col_val, title=''),
                            y=alt.Y('Area', sort='-x', title='', axis=alt.Axis(labelLimit=0)),
                            tooltip=['Area', alt.Tooltip(col_val, format=simbolo_moneda)]
                        ).properties(height=350)
                        st.altair_chart(grafico_areas, use_container_width=True)

                with col_g2:
                    st.markdown(f"**Salud del Embudo ({moneda_sel})**")
                    df_graf_fases = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
                    df_graf_fases = df_graf_fases[df_graf_fases[col_val] > 0]
                    if not df_graf_fases.empty:
                        grafico_barras = alt.Chart(df_graf_fases).mark_bar(color='#2ecc71').encode(
                            x=alt.X(col_val, title=''),
                            y=alt.Y('Fase_Pipeline', sort='-x', title='', axis=alt.Axis(labelLimit=0)),
                            tooltip=['Fase_Pipeline', alt.Tooltip(col_val, format=simbolo_moneda)]
                        ).properties(height=350)
                        st.altair_chart(grafico_barras, use_container_width=True)
                
                st.divider()

                col_g3, col_g4 = st.columns(2)
                
                with col_g3:
                    st.markdown(f"**Composición por Pilar Estratégico**")
                    df_graf_pilares = df.groupby('Pilar_Estrategico')[col_val].sum().reset_index()
                    df_graf_pilares = df_graf_pilares[df_graf_pilares[col_val] > 0]
                    if not df_graf_pilares.empty:
                        grafico_pastel = alt.Chart(df_graf_pilares).mark_arc(innerRadius=60).encode(
                            theta=alt.Theta(field=col_val, type="quantitative"),
                            color=alt.Color(field="Pilar_Estrategico", type="nominal", legend=alt.Legend(title="Pilares", orient="bottom")),
                            tooltip=['Pilar_Estrategico', alt.Tooltip(col_val, format=simbolo_moneda)]
                        ).properties(height=350)
                        st.altair_chart(grafico_pastel, use_container_width=True)

                with col_g4:
                    st.markdown(f"**Forecast por Marcas ({moneda_sel})**")
                    df_marcas = df[df['Marca_Detectada'] != "Multimarca / No Especificada"].groupby('Marca_Detectada')[col_val].sum().reset_index()
                    df_marcas = df_marcas[df_marcas[col_val] > 0]
                    if not df_marcas.empty:
                        grafico_marcas = alt.Chart(df_marcas).mark_bar(color='#e67e22').encode(
                            x=alt.X(col_val, title=''),
                            y=alt.Y('Marca_Detectada', sort='-x', title='', axis=alt.Axis(labelLimit=0)),
                            tooltip=['Marca_Detectada', alt.Tooltip(col_val, format=simbolo_moneda)]
                        ).properties(height=350)
                        st.altair_chart(grafico_marcas, use_container_width=True)

        # ==========================================
        # TAB 2: ENABLEMENT (TABLA DE AUDITORÍA RESTAURADA)
        # ==========================================
        with tab_enablement:
            st.markdown("### Riesgo Operativo y Proyectos Estancados")
            st.caption("Proyectos que requieren apalancamiento estratégico o descarte inmediato.")
            
            estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Monto_USD', ascending=False)
            if not estancados.empty:
                for _, row in estancados.head(4).iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['ID_Proyecto']} | {row['Cliente']}**")
                        st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Riesgo: **${row['Monto_USD']:,.2f} USD**")
                        if st.button(f"Analizar Estrategia 360", key=f"btn_{row['ID_Proyecto']}"):
                            st.session_state.proyecto_foco = str(row['ID_Proyecto'])
                            st.success("Proyecto enviado. Abre la Pestaña 3.")
            else:
                st.success("Embudo limpio. No hay proyectos estancados.")
                
            st.divider()
            st.markdown("#### Base de Datos (Auditoría Rápida)")
            # TABLA DE AUDITORÍA RESTAURADA
            st.dataframe(
                df[['ID_Proyecto', 'Cliente', 'Descripcion', 'Cotizacion', 'Fase_Pipeline', 'Monto_USD', 'Monto_MXN']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID_Proyecto": st.column_config.TextColumn("ID", width="small"),
                    "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
                    "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
                    "Cotizacion": st.column_config.TextColumn("Folio(s)", width="small"),
                    "Fase_Pipeline": st.column_config.TextColumn("Fase", width="small"),
                    "Monto_USD": st.column_config.NumberColumn("USD", format="$%.2f", width="small"),
                    "Monto_MXN": st.column_config.NumberColumn("MXN", format="$%.2f", width="small")
                }
            )

        # ==========================================
        # TAB 3: LABORATORIO TÁCTICO (VISIÓN 360°)
        # ==========================================
        with tab_scott:
            st.markdown("### Copiloto Comercial B2B (Visión 360° Simultánea)")
            st.caption("Aplica MEDDPICC/SPIN Selling a tu oportunidad para obtener todos los canales de ataque de un solo golpe.")
            
            opciones_proyectos = df.apply(lambda x: f"[{x['ID_Proyecto']}] {x['Cliente']} - {str(x['Descripcion'])[:60]}...", axis=1).tolist()
            opciones_proyectos.insert(0, "-- Selecciona un proyecto clave --")
            
            index_default = 0
            if st.session_state.proyecto_foco:
                for i, opcion in enumerate(opciones_proyectos):
                    if f"[{st.session_state.proyecto_foco}]" in opcion:
                        index_default = i; break
            
            seleccion = st.selectbox("Seleccionar Proyecto Objetivo:", opciones_proyectos, index=index_default)
            
            if seleccion != "-- Selecciona un proyecto clave --":
                id_seleccionado = seleccion.split("]")[0].replace("[", "")
                datos_proy = df[df['ID_Proyecto'].astype(str) == id_seleccionado].iloc[0]
                
                st.markdown(f"""
                <div class="ficha-scott">
                    <h4>{datos_proy['Cliente']} (Folio: {datos_proy['ID_Proyecto']})</h4>
                    <b>Equipo:</b> <span style='color:#003a70;'>{datos_proy['Descripcion']}</span> | 
                    <b>Monto:</b> ${datos_proy['Monto_USD']:,.2f} USD
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1: interlocutor = st.selectbox("Perfil del Interlocutor:", ["Ingeniero / Calidad / Mantenimiento", "Comprador / Finanzas / Gerente Planta"])
                with col2: contexto_manual = st.text_input("Notas de situación actual (Ej. 'El cliente compara con Zeiss y le urge'): ")
                
                if gemini_activo:
                    if st.button("🧠 Generar Estrategia 360°", type="primary", use_container_width=True):
                        with st.spinner("Analizando con MEDDPICC, SPIN y lenguaje metrológico..."):
                            try:
                                safety_settings = [
                                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                                ]

                                model = genai.GenerativeModel("gemini-3.6-flash", generation_config={"temperature": 0.3, "max_output_tokens": 2500, "top_p": 0.8})

                                prompt_maestro = f"""
                                Eres Javier Camacho, ejecutivo B2B top de MESS Servicios Metrológicos.
                                
                                CONTEXTO DEL PROYECTO:
                                Cliente: {datos_proy['Cliente']} (Perfil: {interlocutor})
                                Equipo: {datos_proy['Descripcion']}
                                Monto: ${datos_proy['Monto_USD']} USD
                                Notas: {contexto_manual}
                                
                                INSTRUCCIÓN METODOLÓGICA:
                                1. Si el monto es menor a $1,500 USD, tu tono debe ser Sandler: Cierre rápido, directo, transaccional. Ir al "No" rápido.
                                2. Si el monto es mayor a $1,500 USD, tu tono debe basarse en MEDDPICC (Métricas, Champion, Proceso de Decisión) y SPIN Selling (Preguntas de Implicación).
                                3. Usa terminología de metrología industrial: "Incertidumbre de medición", "GD&T", "Trazabilidad", "Resolución", "Acreditación ISO/IEC 17025", etc.
                                
                                FORMATO DE SALIDA ESTRICTO (6 BLOQUES OBLIGATORIOS):
                                Separa tu respuesta usando ESTOS EXACTOS MARCADORES. Asegúrate de incluir el marcador antes de empezar a redactar cada sección. No uses viñetas ni asteriscos en los marcadores.

                                SECCION_ANALISIS:
                                (Análisis de la cuenta B2B usando las metodologías).

                                SECCION_WHATSAPP:
                                (Mensaje ágil y estructurado para WhatsApp. Lenguaje metrológico directo).

                                SECCION_CORREO:
                                (Correo formal con Asunto. Basado en Implicación/SPIN).

                                SECCION_LLAMADA:
                                (Guion para llamada de 1 minuto).

                                SECCION_MARKETING:
                                (Instrucción concreta de ABM para el departamento de Marketing).

                                SECCION_BITACORA:
                                (Reporte súper técnico para pegar en el CRM SCOTT).
                                """
                                
                                response = model.generate_content(prompt_maestro, safety_settings=safety_settings)
                                texto_raw = response.text
                                
                                s1 = re.search(r'SECCION_ANALISIS:(.*?)(?=SECCION_WHATSAPP:)', texto_raw, re.DOTALL | re.IGNORECASE)
                                s2 = re.search(r'SECCION_WHATSAPP:(.*?)(?=SECCION_CORREO:)', texto_raw, re.DOTALL | re.IGNORECASE)
                                s3 = re.search(r'SECCION_CORREO:(.*?)(?=SECCION_LLAMADA:)', texto_raw, re.DOTALL | re.IGNORECASE)
                                s4 = re.search(r'SECCION_LLAMADA:(.*?)(?=SECCION_MARKETING:)', texto_raw, re.DOTALL | re.IGNORECASE)
                                s5 = re.search(r'SECCION_MARKETING:(.*?)(?=SECCION_BITACORA:)', texto_raw, re.DOTALL | re.IGNORECASE)
                                s6 = re.search(r'SECCION_BITACORA:(.*)', texto_raw, re.DOTALL | re.IGNORECASE)

                                st.session_state.tactica_analisis = s1.group(1).strip() if s1 else "Error aislando sección."
                                st.session_state.tactica_whatsapp = s2.group(1).strip() if s2 else "Error aislando sección."
                                st.session_state.tactica_correo = s3.group(1).strip() if s3 else "Error aislando sección."
                                st.session_state.tactica_llamada = s4.group(1).strip() if s4 else "Error aislando sección."
                                st.session_state.tactica_marketing = s5.group(1).strip() if s5 else "Error aislando sección."
                                st.session_state.tactica_bitacora = s6.group(1).strip() if s6 else "Error aislando sección."
                                
                                if not s1: st.session_state.tactica_analisis = texto_raw
                                
                                st.session_state.tactica_cliente = datos_proy['Cliente']
                                st.session_state.tactica_id = datos_proy['ID_Proyecto']
                                st.session_state.tactica_equipo = datos_proy['Descripcion']
                                st.session_state.tactica_monto = f"${datos_proy['Monto_USD']:,.2f} USD"
                                
                            except Exception as e:
                                st.error(f"Error de IA: {e}")

                if st.session_state.tactica_whatsapp:
                    st.success("Arsenal táctico generado con éxito.")
                    
                    colA, colB = st.columns(2)
                    with colA:
                        st.markdown("#### 🧠 Análisis MEDDPICC / SPIN")
                        st.info(st.session_state.tactica_analisis)
                        
                        st.markdown("#### 📲 Mensaje WhatsApp")
                        st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_whatsapp}</div>", unsafe_allow_html=True)
                        if st.button("📱 Enviar a WhatsApp"):
                            st.link_button("Abrir Web", f"https://wa.me/?text={urllib.parse.quote(st.session_state.tactica_whatsapp)}")
                        
                        st.markdown("#### 📞 Guion Llamada")
                        st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_llamada}</div>", unsafe_allow_html=True)

                    with colB:
                        st.markdown("#### ✉️ Correo Electrónico")
                        st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_correo}</div>", unsafe_allow_html=True)
                        if st.button("📧 Redactar Correo"):
                            st.link_button("Abrir Mail", f"mailto:?subject=Seguimiento Proyecto {st.session_state.tactica_id}&body={urllib.parse.quote(st.session_state.tactica_correo)}")
                        
                        st.markdown("#### 🎯 Solicitud Marketing (ABM)")
                        st.warning(st.session_state.tactica_marketing)
                        
                        st.markdown("#### 📋 Bitácora CRM (SCOTT)")
                        st.success(st.session_state.tactica_bitacora)
                        
                    if docx_disponible:
                        st.divider()
                        st.markdown("### 📤 Exportar Documento 360°")
                        def exportar_todo():
                            doc = Document()
                            doc.add_heading("ARSENAL TÁCTICO 360° | REVENUE OPERATIONS", 0)
                            doc.add_heading("Contexto del Proyecto", 1)
                            doc.add_paragraph(f"Cliente: {st.session_state.tactica_cliente}\nFolio: {st.session_state.tactica_id}\nEquipo: {st.session_state.tactica_equipo}\nValor: {st.session_state.tactica_monto}")
                            doc.add_heading("1. Análisis MEDDPICC/SPIN", 1)
                            doc.add_paragraph(st.session_state.tactica_analisis)
                            doc.add_heading("2. WhatsApp", 1)
                            doc.add_paragraph(st.session_state.tactica_whatsapp)
                            doc.add_heading("3. Correo Electrónico", 1)
                            doc.add_paragraph(st.session_state.tactica_correo)
                            doc.add_heading("4. Guion Telefónico", 1)
                            doc.add_paragraph(st.session_state.tactica_llamada)
                            doc.add_heading("5. Marketing ABM", 1)
                            doc.add_paragraph(st.session_state.tactica_marketing)
                            doc.add_heading("6. Registro CRM", 1)
                            doc.add_paragraph(st.session_state.tactica_bitacora)
                            buffer = io.BytesIO()
                            doc.save(buffer)
                            buffer.seek(0)
                            return buffer

                        st.download_button("💾 Descargar Estrategia Completa (.docx)", data=exportar_todo(), file_name=f"Estrategia360_{st.session_state.tactica_id}.docx", use_container_width=True)
    except Exception as e:
        st.error(f"Error procesando CSV: {e}")
else:
    with tab_dashboards: st.warning("Sube el archivo CSV del CRM SCOTT en la barra lateral para ver tus datos.")
    with tab_enablement: st.warning("Requiere datos.")
    with tab_scott: st.warning("Requiere datos.")

# ==========================================
# TAB 4: MÓDULO MEDDPICC (EXPLICADO)
# ==========================================
with tab_meddpicc:
    st.markdown("### Auditoría de Calificación B2B (Framework MEDDPICC)")
    
    # CUADRO EXPLICATIVO PARA EVITAR CONFUSIONES
    st.info("""
    💡 **¿Qué es este Dashboard y de dónde salen estos datos?**
    Actualmente el sistema CRM SCOTT no cuenta con casillas para calificar metodologías avanzadas. Por lo tanto, los datos que ves a continuación **son simulados** (ej. Ford, Tremec, BRP) para demostrar cómo se visualizaría tu embudo si pudieras medir el "Health Score" (Nivel de Salud) de tus proyectos utilizando la metodología MEDDPICC.
    """)
    
    col_f1, col_f2 = st.columns(2)
    with col_f1: 
        fases_disp = df_meddpicc['Etapa_Pipeline'].unique()
        filtro_etapa = st.multiselect("Filtrar por Etapa de Pipeline (Simulado):", sorted(fases_disp), default=sorted(fases_disp))
    with col_f2: 
        score_min = st.slider("Health Score Mínimo (Suma MEDDPICC):", 0, 16, 0)
        
    df_filtrado = df_meddpicc[(df_meddpicc['Etapa_Pipeline'].isin(filtro_etapa)) & (df_meddpicc['Health_Score'] >= score_min)]
    
    if not df_filtrado.empty:
        val_total = df_filtrado['Valor_USD'].sum()
        avg_score = df_filtrado['Health_Score'].mean()
        riesgos = df_filtrado[(df_filtrado['Etapa_Pipeline'] >= 4) & (df_filtrado['Health_Score'] < 10)].shape[0]
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Valor Total del Pipeline (Simulado)", f"${val_total:,.0f} USD")
        k2.metric("Promedio Health Score", f"{avg_score:.1f} / 16")
        k3.metric("Oportunidades en Riesgo Crítico", f"{riesgos} cuentas", "Etapa Avanzada + Score Bajo")
        
        st.divider()
        
        st.markdown("#### Matriz de Dispersión: Madurez vs. Riesgo")
        st.caption("Los proyectos que están muy avanzados en etapa (Ej. 4 o 5) pero con una calificación MEDDPICC baja (rojos) corren un alto riesgo de caerse.")
        color_map = {'Riesgo Alto': '#e74c3c', 'Precaución': '#f1c40f', 'Saludable': '#2ecc71'}
        
        fig_scatter = px.scatter(
            df_filtrado, 
            x="Etapa_Pipeline", 
            y="Health_Score", 
            size="Valor_USD", 
            color="Estado",
            color_discrete_map=color_map,
            hover_name="Oportunidad",
            hover_data={"Valor_USD": ':,.0f', "Etapa_Pipeline": True, "Estado": False},
            size_max=45,
            labels={'Etapa_Pipeline': 'Etapa del CRM (1-5)', 'Health_Score': 'Health Score MEDDPICC (0-16)'}
        )
        fig_scatter.add_hrect(y0=0, y1=8, line_width=0, fillcolor="red", opacity=0.05)
        fig_scatter.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.divider()
        
        st.markdown("#### Matriz de Calor (Puntos Ciegos MEDDPICC)")
        st.caption("Este mapa te muestra qué información crucial te falta averiguar para asegurar la venta. (Rojo: Desconocido | Amarillo: Identificado | Verde: Validado)")
        
        df_heat = df_filtrado.sort_values(by="Valor_USD", ascending=True)
        z_data = df_heat[['M','E','D1','D2','P','I','C1','C2']].values
        y_labels = df_heat['Oportunidad'].tolist()
        x_labels = ['M (Métricas)', 'E (Econ. Buyer)', 'D1 (Criteria)', 'D2 (Process)', 'P (Paperwork)', 'I (Implicación)', 'C1 (Champion)', 'C2 (Competencia)']
        
        fig_heat = go.Figure(data=go.Heatmap(
            z=z_data,
            x=x_labels,
            y=y_labels,
            colorscale=[[0, '#e74c3c'], [0.5, '#f1c40f'], [1, '#2ecc71']],
            showscale=False,
            text=z_data,
            texttemplate="%{text}",
            textfont={"size":14, "color":"white"}
        ))
        fig_heat.update_layout(height=max(300, len(y_labels)*50), margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("No hay oportunidades que coincidan con los filtros de la auditoría MEDDPICC.")
