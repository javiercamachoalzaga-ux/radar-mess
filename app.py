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
if 'tactica_mensaje' not in st.session_state: st.session_state.tactica_mensaje = ""
if 'tactica_objeciones' not in st.session_state: st.session_state.tactica_objeciones = ""
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
tab_dashboards, tab_enablement, tab_scott = st.tabs([
    "1. Dashboards CRM", 
    "2. Proyectos Estancados", 
    "3. Laboratorio IA (Estrategia Integral)"
])

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])

if archivo_cargado is not None:
    try:
        # --- LECTOR ROBUSTO SCOTT ---
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
            
        df_data = df_data.dropna(subset=['PROYECTO']).reset_index(drop=True)

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_data.columns:
                    if str(col).upper().strip() == clave or str(col).upper().strip() == f"{clave}.1":
                        return df_data[col].copy()
            return pd.Series([None] * len(df_data))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def sanear_y_limpiar(texto):
            if pd.isna(texto): return ""
            return re.sub(r'\s+', ' ', str(texto).replace("?", "ó")).strip().title()

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
            'Cliente_Final': 'first', 'Area': 'first', 'Fecha_Creacion': 'first', 'Fecha_Cierre': 'first',
            'Estatus': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum', 'Monto_USD': 'sum'
        }).reset_index()

        df.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        df = df[(df['Monto_MXN'] > 0) | (df['Monto_USD'] > 0)]
        filtro_estatus = df['Estatus'].str.contains('PROCESO', case=False, na=False)
        filtro_etapa = df['Etapa'].str.contains('PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)
        df = df[filtro_estatus | filtro_etapa].copy()
        
        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]): return "1. Alta Gama"
            elif any(k in texto for k in ["CALIBRACIÓN", "LABORATORIO", "DIMENSIONAL"]): return "2. Calibraciones"
            else: return "3. Productos Generales"
        
        df['Pilar_Estrategico'] = df.apply(clasificar_pilar, axis=1)
        
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

        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        opciones_pilares = df['Pilar_Estrategico'].unique().tolist()
        filtro_pilar = st.sidebar.multiselect("Filtrar por Pilar:", opciones_pilares, default=opciones_pilares)
        busqueda_proyecto = st.sidebar.text_input("Buscar Folio o Cliente:")
        
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]
        if filtro_pilar:
            df = df[df['Pilar_Estrategico'].isin(filtro_pilar)]

        mes_actual, anio_actual = pd.Timestamp.now().month, pd.Timestamp.now().year

        # ==========================================
        # TAB 1: DASHBOARDS CRM
        # ==========================================
        with tab_dashboards:
            st.markdown("### Análisis de Forecast vs Cuota ($80K USD)")
            META_MENSUAL_USD = 80000.00
            
            df_mes = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)]
            usd_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_USD'].sum()
            mxn_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_MXN'].sum()
            
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("Meta Comercial Mensual", f"${META_MENSUAL_USD:,.2f} USD")
            col_g2.metric("Pipeline Probable (USD)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN extra")
            if (META_MENSUAL_USD - usd_caliente) > 0:
                col_g3.metric("GAP (Brecha para Meta)", f"${(META_MENSUAL_USD - usd_caliente):,.2f} USD", "- Acción requerida")
            else:
                col_g3.metric("GAP (Brecha)", "$0.00 USD", "+ Meta Cubierta")
            
            st.divider()
            col_sel1, col_sel2 = st.columns([1, 3])
            with col_sel1: moneda_sel = st.selectbox("Seleccionar Moneda para Gráficos:", ["USD ($)", "MXN ($)"])
            col_val = 'Monto_USD' if moneda_sel == "USD ($)" else 'Monto_MXN'
            
            st.divider()
            
            if not df.empty:
                st.markdown(f"#### Análisis Pareto 80/20 por Cuentas Clave ({moneda_sel})")
                df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
                df_pareto = df_pareto[df_pareto[col_val] > 0].sort_values(by=col_val, ascending=False).reset_index(drop=True)
                if not df_pareto.empty:
                    df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
                    df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
                    
                    barras_pareto = alt.Chart(df_pareto).mark_bar(color='#34495e').encode(
                        x=alt.X('Cliente', sort=None, title='Cliente', axis=alt.Axis(labelLimit=0)),
                        y=alt.Y(col_val, title=f'Valor'),
                        tooltip=['Cliente', alt.Tooltip(col_val, format='$,.2f'), alt.Tooltip('Porcentaje', format='.1%')]
                    )
                    linea_pareto = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(
                        x=alt.X('Cliente', sort=None),
                        y=alt.Y('Acumulado', title='Porcentaje Acumulado', axis=alt.Axis(format='%')),
                        tooltip=['Cliente', alt.Tooltip('Acumulado', format='.1%')]
                    )
                    st.altair_chart(alt.layer(barras_pareto, linea_pareto).resolve_scale(y='independent').properties(height=450), use_container_width=True)
                
                st.divider()
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown(f"**Forecast por Área**")
                    df_areas = df.groupby('Area')[col_val].sum().reset_index()
                    if not df_areas.empty: st.altair_chart(alt.Chart(df_areas[df_areas[col_val]>0]).mark_bar(color='#003a70').encode(x=alt.X(col_val, title=''), y=alt.Y('Area', sort='-x', title=''), tooltip=['Area', alt.Tooltip(col_val, format='$,.2f')]).properties(height=350), use_container_width=True)
                with col_g2:
                    st.markdown(f"**Salud del Embudo**")
                    df_graf_fases = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
                    if not df_graf_fases.empty: st.altair_chart(alt.Chart(df_graf_fases[df_graf_fases[col_val]>0]).mark_bar(color='#2ecc71').encode(x=alt.X(col_val, title=''), y=alt.Y('Fase_Pipeline', sort='-x', title=''), tooltip=['Fase_Pipeline', alt.Tooltip(col_val, format='$,.2f')]).properties(height=350), use_container_width=True)

        # ==========================================
        # TAB 2: ENABLEMENT
        # ==========================================
        with tab_enablement:
            st.markdown("### Riesgo Operativo y Proyectos Estancados")
            estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Monto_USD', ascending=False)
            if not estancados.empty:
                for _, row in estancados.head(4).iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['ID_Proyecto']} | {row['Cliente']}**")
                        st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Riesgo: **${row['Monto_USD']:,.2f} USD**")
            else:
                st.success("Embudo limpio.")
                
            st.divider()
            st.markdown("#### Auditoría Rápida CRM")
            st.dataframe(df[['ID_Proyecto', 'Cliente', 'Descripcion', 'Fase_Pipeline', 'Monto_USD']], use_container_width=True, hide_index=True)

        # ==========================================
        # TAB 3: LABORATORIO TÁCTICO IA (EMPAQUETADOR Y LENGUAJE HUMANO)
        # ==========================================
        with tab_scott:
            st.markdown("### Copiloto Estratégico (Key Account Management)")
            st.caption("Arma estrategias para un proyecto único o consolida varios proyectos en una sola negociación de paquete.")
            
            # --- 1. SELECCIÓN DE CLIENTE ---
            clientes_disponibles = sorted(df['Cliente'].unique().tolist())
            cliente_seleccionado = st.selectbox("1. Selecciona la Cuenta / Cliente:", ["-- Selecciona un cliente --"] + clientes_disponibles)
            
            if cliente_seleccionado != "-- Selecciona un cliente --":
                df_cliente = df[df['Cliente'] == cliente_seleccionado]
                
                # --- 2. MULTI-SELECCIÓN DE PROYECTOS ---
                opciones_proyectos_cliente = df_cliente.apply(lambda x: f"[{x['ID_Proyecto']}] {str(x['Descripcion'])} - ${x['Monto_USD']:,.0f} USD", axis=1).tolist()
                proyectos_seleccionados = st.multiselect("2. Selecciona los folios a incluir en esta estrategia (Puedes elegir varios):", opciones_proyectos_cliente)
                
                if proyectos_seleccionados:
                    # Extraer IDs y filtrar
                    ids_seleccionados = [opc.split("]")[0].replace("[", "") for opc in proyectos_seleccionados]
                    df_seleccion = df[df['ID_Proyecto'].astype(str).isin(ids_seleccionados)]
                    
                    # Consolidar datos
                    monto_total_usd = df_seleccion['Monto_USD'].sum()
                    equipos_combinados = " | ".join(df_seleccion['Descripcion'].tolist())
                    ids_combinados = ", ".join(df_seleccion['ID_Proyecto'].astype(str).tolist())
                    es_paquete = len(df_seleccion) > 1
                    
                    st.markdown(f"""
                    <div class="ficha-scott">
                        <h4>{cliente_seleccionado} (Folios: {ids_combinados})</h4>
                        <b>Equipos Involucrados:</b> <span style='color:#003a70;'>{equipos_combinados}</span><br>
                        <b>Monto Total a Negociar:</b> <span style='color:#27ae60; font-weight:bold; font-size:18px;'>${monto_total_usd:,.2f} USD</span>
                        {'<br><span style="color:#e67e22; font-weight:bold;">⚠️ Estrategia de Paquete (Bundle) Activada</span>' if es_paquete else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("#### Configuración de la Táctica")
                    tipo_operacion = st.radio("Objetivo Principal:", ["Aceleración y Cierre (Virtual)", "Apertura y Visitas (Presencial)"], horizontal=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        if tipo_operacion == "Aceleración y Cierre (Virtual)":
                            sub_opcion = st.radio("¿Qué canal vas a usar?", ["Mensaje de WhatsApp", "Correo Electrónico Ejecutivo", "Guion de Llamada Telefónica"])
                        else:
                            sub_opcion = st.radio("¿Qué tipo de visita harás?", [
                                "Visita de Prospección (Primer Contacto)",
                                "Visita Técnica (Acompañado de Product Manager)",
                                "Visita Estratégica / Negociación (Con Gerencia o Dirección)"
                            ])
                        interlocutor = st.selectbox("Perfil del Interlocutor:", ["Ingeniero / Calidad / Mantenimiento", "Comprador / Finanzas / Gerente Planta", "Director / Dueño"])
                    
                    with col2: 
                        giro_cliente = st.text_input("Giro o Terminología del cliente (Ej. 'Usar casting, no fundición. Sector Aeroespacial'):", placeholder="Sector, términos clave a usar o evitar...")
                        contexto_manual = st.text_area("Notas de situación actual (Ej. 'Están evaluando a Zeiss, no tienen presupuesto liberado'):", height=100)
                    
                    if gemini_activo:
                        if st.button("🧠 Generar Estrategia Consultiva", type="primary", use_container_width=True):
                            with st.spinner("Diseñando estrategia empática y consolidando información en formato estricto..."):
                                try:
                                    safety_settings = [
                                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                                    ]

                                    model = genai.GenerativeModel("gemini-3.6-flash", generation_config={"temperature": 0.4, "max_output_tokens": 2500, "top_p": 0.8})

                                    prompt_maestro = f"""
                                    Eres Javier Camacho, un Asesor Consultivo B2B y Key Account Manager de MESS Servicios Metrológicos.
                                    
                                    CONTEXTO DE LA NEGOCIACIÓN:
                                    Cliente: {cliente_seleccionado} (Perfil: {interlocutor})
                                    Giro e Instrucciones de Terminología: {giro_cliente}
                                    Equipos/Servicios: {equipos_combinados}
                                    Monto Total: ${monto_total_usd} USD
                                    Proyectos Agrupados: {len(df_seleccion)}
                                    Acción Solicitada: {sub_opcion}
                                    Notas Adicionales: {contexto_manual}
                                    
                                    DIRECTRICES DE TONO (MANDATORIO POR DIRECCIÓN GENERAL):
                                    - COMUNICACIÓN HUMANIZADA: Escribe de humano a humano. Sé profesional, empático, natural y conversacional.
                                    - CERO EXAGERACIÓN TÉCNICA: No uses términos rimbombantes. Menciona la técnica de forma sutil solo si el cliente la requiere para entender el valor.
                                    - ADAPTACIÓN AL GIRO: Respeta estrictamente el giro y la terminología indicada. No inventes procesos industriales que no aplican.
                                    - SI HAY MÚLTIPLES PROYECTOS: Tu estrategia DEBE enfocarse en vender esto como un "Paquete" o "Solución Integral" (Bundle) para facilitar la decisión del cliente y negociar mejores condiciones globales.
                                    
                                    INTEGRACIÓN METODOLÓGICA INVISIBLE:
                                    Usa MEDDPICC para mapear la cuenta, SPIN para tocar el dolor, y Sandler para el cierre (buscar el sí/no claro sin rogar). Aplícalo en el análisis y en los mensajes de forma invisible y fluida.
                                    
                                    FORMATO DE SALIDA ESTRICTO (JSON):
                                    Devuelve ÚNICAMENTE un objeto JSON válido con las siguientes claves exactas en minúscula. Todo el contenido dentro de los valores del JSON debe estar redactado en ESPAÑOL. No incluyas comillas triples (```) ni texto adicional fuera del JSON:
                                    {{
                                      "analisis": "(Análisis estratégico humano. Evalúa la cuenta y explica cómo vender la solución (o el paquete si son varios). Define cómo usar Sandler aquí.)",
                                      "mensaje": "(Redacta el texto exacto para el canal seleccionado: {sub_opcion}. Muy humano, claro, empático y al punto.)",
                                      "objeciones": "(Menciona 2 posibles objeciones del cliente ante esta propuesta y cómo rebatirlas como consultor experto, no como folleto.)",
                                      "marketing": "(Instrucción para el equipo de Marketing sobre qué material de apoyo enviar para esta cuenta/giro)",
                                      "bitacora": "(Reporte súper breve para pegar en el CRM SCOTT)"
                                    }}
                                    """
                                    
                                    response = model.generate_content(prompt_maestro, safety_settings=safety_settings)
                                    texto_raw = response.text.strip()
                                    
                                    # Limpiar código markdown de la respuesta de Gemini
                                    if texto_raw.startswith("```json"): texto_raw = texto_raw[7:]
                                    if texto_raw.startswith("```"): texto_raw = texto_raw[3:]
                                    if texto_raw.endswith("```"): texto_raw = texto_raw[:-3]
                                    texto_raw = texto_raw.strip()
                                    
                                    try:
                                        datos_json = json.loads(texto_raw)
                                        st.session_state.tactica_analisis = datos_json.get("analisis", "Dato no generado por la IA.")
                                        st.session_state.tactica_mensaje = datos_json.get("mensaje", "Dato no generado por la IA.")
                                        st.session_state.tactica_objeciones = datos_json.get("objeciones", "Dato no generado por la IA.")
                                        st.session_state.tactica_marketing = datos_json.get("marketing", "Dato no generado por la IA.")
                                        st.session_state.tactica_bitacora = datos_json.get("bitacora", "Dato no generado por la IA.")
                                    except json.JSONDecodeError:
                                        st.error("La IA generó una respuesta que no pudo ser procesada estructuralmente. Intenta nuevamente.")
                                        st.session_state.tactica_mensaje = ""
                                    
                                    if st.session_state.tactica_mensaje:
                                        st.session_state.tactica_cliente = cliente_seleccionado
                                        st.session_state.tactica_id = ids_combinados
                                        st.session_state.tactica_equipo = equipos_combinados
                                        st.session_state.tactica_monto = f"${monto_total_usd:,.2f} USD"
                                    
                                except Exception as e:
                                    st.error(f"Error de IA: {e}")

                    # VISTA DE RESULTADOS
                    if st.session_state.tactica_mensaje:
                        st.success(f"Estrategia Consultiva generada con éxito para: {sub_opcion}")
                        
                        st.markdown("#### 🧠 Análisis Estratégico (KAM / Empaquetado)")
                        st.info(st.session_state.tactica_analisis)
                        
                        st.markdown(f"#### 💬 Acción Ejecutada: {sub_opcion}")
                        st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_mensaje}</div>", unsafe_allow_html=True)
                        
                        st.markdown("#### 🛡️ Manejo de Objeciones")
                        st.warning(st.session_state.tactica_objeciones)
                        
                        st.markdown("#### 🎯 Solicitud Marketing (ABM)")
                        st.info(st.session_state.tactica_marketing)
                        
                        st.markdown("#### 📋 Bitácora CRM (SCOTT)")
                        st.success(st.session_state.tactica_bitacora)
                            
                        if docx_disponible:
                            st.divider()
                            st.markdown("### 📤 Exportar Documento")
                            def exportar_todo():
                                doc = Document()
                                doc.add_heading("ESTRATEGIA KAM | REVENUE OPERATIONS", 0)
                                doc.add_paragraph(f"Cliente: {st.session_state.tactica_cliente}\nFolios Agrupados: {st.session_state.tactica_id}\nEquipos/Servicios: {st.session_state.tactica_equipo}\nValor Total: {st.session_state.tactica_monto}")
                                doc.add_heading("1. Análisis Estratégico", 1)
                                doc.add_paragraph(st.session_state.tactica_analisis)
                                doc.add_heading(f"2. Acción: {sub_opcion}", 1)
                                doc.add_paragraph(st.session_state.tactica_mensaje)
                                doc.add_heading("3. Manejo de Objeciones", 1)
                                doc.add_paragraph(st.session_state.tactica_objeciones)
                                doc.add_heading("4. Marketing ABM", 1)
                                doc.add_paragraph(st.session_state.tactica_marketing)
                                doc.add_heading("5. Registro CRM", 1)
                                doc.add_paragraph(st.session_state.tactica_bitacora)
                                buffer = io.BytesIO()
                                doc.save(buffer)
                                buffer.seek(0)
                                return buffer

                            st.download_button("💾 Descargar Estrategia Completa (.docx)", data=exportar_todo(), file_name=f"EstrategiaKAM_{st.session_state.tactica_cliente.replace(' ','_')}.docx", use_container_width=True)
    except Exception as e:
        st.error(f"Error procesando CSV: {e}")
else:
    with tab_dashboards: st.warning("Sube el archivo CSV del CRM SCOTT en la barra lateral para ver tus datos.")
    with tab_enablement: st.warning("Requiere datos.")
    with tab_scott: st.warning("Requiere datos.")
