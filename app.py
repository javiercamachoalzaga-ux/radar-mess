import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
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
# TABS DE NAVEGACIÓN (AHORA SON SOLO 3)
# ==========================================
tab_dashboards, tab_enablement, tab_scott = st.tabs([
    "1. Dashboards CRM", 
    "2. Proyectos Estancados", 
    "3. Laboratorio IA"
])

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
        
        # CLASIFICACIÓN
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
        # TAB 1: DASHBOARDS
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
            simbolo_moneda = '$,.2f'
            
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
                        y=alt.Y(col_val, title=f'Valor {moneda_sel}'),
                        tooltip=['Cliente', alt.Tooltip(col_val, format=simbolo_moneda), alt.Tooltip('Porcentaje', format='.1%')]
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
                    st.markdown(f"**Forecast por Área ({moneda_sel})**")
                    df_areas = df.groupby('Area')[col_val].sum().reset_index()
                    if not df_areas.empty: st.altair_chart(alt.Chart(df_areas[df_areas[col_val]>0]).mark_bar(color='#003a70').encode(x=alt.X(col_val, title=''), y=alt.Y('Area', sort='-x', title='', axis=alt.Axis(labelLimit=0)), tooltip=['Area', alt.Tooltip(col_val, format=simbolo_moneda)]).properties(height=350), use_container_width=True)
                with col_g2:
                    st.markdown(f"**Salud del Embudo ({moneda_sel})**")
                    df_graf_fases = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
                    if not df_graf_fases.empty: st.altair_chart(alt.Chart(df_graf_fases[df_graf_fases[col_val]>0]).mark_bar(color='#2ecc71').encode(x=alt.X(col_val, title=''), y=alt.Y('Fase_Pipeline', sort='-x', title='', axis=alt.Axis(labelLimit=0)), tooltip=['Fase_Pipeline', alt.Tooltip(col_val, format=simbolo_moneda)]).properties(height=350), use_container_width=True)

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
                        if st.button(f"Analizar en Laboratorio IA", key=f"btn_{row['ID_Proyecto']}"):
                            st.session_state.proyecto_foco = str(row['ID_Proyecto'])
                            st.success("Proyecto enviado. Abre la Pestaña 3.")
            else:
                st.success("Embudo limpio.")
                
            st.divider()
            st.markdown("#### Auditoría Rápida CRM")
            st.dataframe(df[['ID_Proyecto', 'Cliente', 'Descripcion', 'Cotizacion', 'Fase_Pipeline', 'Monto_USD']], use_container_width=True, hide_index=True)

        # ==========================================
        # TAB 3: LABORATORIO TÁCTICO IA (OBJECIONES + ETIQUETAS EN INGLÉS)
        # ==========================================
        with tab_scott:
            st.markdown("### Laboratorio Táctico IA (MEDDPICC, SPIN & Sandler)")
            st.caption("Selecciona tu proyecto y define tu estrategia de cierre o visita.")
            
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
                
                tipo_operacion = st.radio("Objetivo Principal de la Táctica:", ["Aceleración y Cierre (Virtual)", "Apertura y Visitas (Presencial)"], horizontal=True)

                col1, col2 = st.columns(2)
                with col1:
                    if tipo_operacion == "Aceleración y Cierre (Virtual)":
                        sub_opcion = st.radio("¿Qué canal vas a usar?", ["Mensaje de WhatsApp", "Correo Electrónico Ejecutivo", "Guion de Llamada Telefónica"])
                    else:
                        sub_opcion = st.radio("¿Qué tipo de visita harás?", [
                            "Visita de Prospección (Primer Contacto)",
                            "Visita Técnica (Acompañado de Product Manager)",
                            "Visita de Negociación (Acompañado de Gerencia - Martín Becerra)",
                            "Visita Estratégica (Acompañado de Dirección - Óscar Morales)"
                        ])
                
                with col2: 
                    interlocutor = st.selectbox("Perfil del Interlocutor:", ["Ingeniero / Calidad / Mantenimiento", "Comprador / Finanzas / Gerente Planta"])
                    contexto_manual = st.text_area("Notas de situación actual (Ej. 'El cliente compara con Zeiss y le urge'): ")
                
                if gemini_activo:
                    if st.button("🧠 Generar Táctica 360° y Manejo de Objeciones", type="primary", use_container_width=True):
                        with st.spinner("Integrando MEDDPICC, SPIN y Sandler. Estructurando análisis..."):
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
                                Acción Solicitada: {sub_opcion}
                                Notas: {contexto_manual}
                                
                                INSTRUCCIÓN METODOLÓGICA (INTEGRACIÓN ESTRATÉGICA):
                                1. ESTRATEGIA BASE (MEDDPICC y SPIN): Evalúa la madurez de la cuenta con MEDDPICC (Economic Buyer, Criterios, Champion) y formula el dolor con SPIN Selling (Preguntas de Implicación).
                                2. ACELERADOR DE CIERRES (SANDLER): Agrega el Método Sandler a tu estrategia para forzar cierres rápidos, ir directo al punto y evitar el desgaste en el seguimiento.
                                3. LENGUAJE TÉCNICO: Usa terminología de metrología industrial: "Incertidumbre de medición", "GD&T", "Trazabilidad", "Resolución", "Acreditación ISO 17025", etc.
                                
                                FORMATO DE SALIDA ESTRICTO (ETIQUETAS XML EN INGLÉS OBLIGATORIAS):
                                Debes estructurar tu respuesta utilizando ÚNICAMENTE las siguientes etiquetas XML en inglés para evitar errores de extracción. El texto adentro de las etiquetas debe ser en ESPAÑOL. No uses Markdown fuera de las etiquetas.

                                <ANALYSIS>
                                (Desarrolla la estrategia inicial detallando cómo aplicar MEDDPICC y SPIN en esta cuenta, y suma explícitamente cómo usar Sandler para un cierre rápido o calificar si vale la pena el esfuerzo).
                                </ANALYSIS>

                                <MESSAGE>
                                (Redacta el texto exacto para el canal seleccionado: {sub_opcion}. Lenguaje empático pero directo al dolor. Si es visita, redacta los puntos a tratar).
                                </MESSAGE>

                                <OBJECTIONS>
                                (Redacta 2 posibles objeciones del cliente basadas en este equipo/monto y cómo rebatirlas estratégicamente con lenguaje metrológico).
                                </OBJECTIONS>

                                <MARKETING>
                                (Instrucción concreta de ABM para el departamento de Marketing, ej. enviar caso de éxito o brochure técnico).
                                </MARKETING>

                                <LOG>
                                (Reporte hiper-resumido y técnico en tercera persona para pegar en el CRM SCOTT).
                                </LOG>
                                """
                                
                                response = model.generate_content(prompt_maestro, safety_settings=safety_settings)
                                texto_raw = response.text
                                
                                # === EXTRACCIÓN XML BLINDADA (ETIQUETAS EN INGLÉS) ===
                                def extract_xml(tag, text):
                                    match = re.search(rf'<{tag}>(.*?)</{tag}>', text, re.DOTALL | re.IGNORECASE)
                                    return match.group(1).strip() if match else "Error aislando sección."

                                st.session_state.tactica_analisis = extract_xml('ANALYSIS', texto_raw)
                                st.session_state.tactica_mensaje = extract_xml('MESSAGE', texto_raw)
                                st.session_state.tactica_objeciones = extract_xml('OBJECTIONS', texto_raw)
                                st.session_state.tactica_marketing = extract_xml('MARKETING', texto_raw)
                                st.session_state.tactica_bitacora = extract_xml('LOG', texto_raw)
                                
                                # Fallback robusto por si la IA ignoró el XML por completo
                                if "Error aislando" in st.session_state.tactica_mensaje:
                                    st.session_state.tactica_mensaje = texto_raw
                                
                                st.session_state.tactica_cliente = datos_proy['Cliente']
                                st.session_state.tactica_id = datos_proy['ID_Proyecto']
                                st.session_state.tactica_equipo = datos_proy['Descripcion']
                                st.session_state.tactica_monto = f"${datos_proy['Monto_USD']:,.2f} USD"
                                
                            except Exception as e:
                                st.error(f"Error de IA: {e}")

                # VISTA DE RESULTADOS
                if st.session_state.tactica_mensaje:
                    st.success(f"Táctica generada con éxito para: {sub_opcion}")
                    
                    st.markdown("#### 🧠 Análisis Estratégico (MEDDPICC + SPIN + Sandler)")
                    st.info(st.session_state.tactica_analisis)
                    
                    st.markdown(f"#### 💬 Acción Ejecutada: {sub_opcion}")
                    st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_mensaje}</div>", unsafe_allow_html=True)
                    
                    st.markdown("#### 🛡️ Manejo de Objeciones")
                    st.warning(st.session_state.tactica_objeciones)
                    
                    st.markdown("#### 🎯 Solicitud Marketing (ABM)")
                    st.info(st.session_state.tactica_marketing)
                    
                    st.markdown("#### 📋 Bitácora CRM (SCOTT)")
                    st.success(st.session_state.tactica_bitacora)
                        
                    # EXPORTACIÓN
                    if docx_disponible:
                        st.divider()
                        st.markdown("### 📤 Exportar Documento")
                        def exportar_todo():
                            doc = Document()
                            doc.add_heading("TÁCTICA B2B | REVENUE OPERATIONS", 0)
                            doc.add_paragraph(f"Cliente: {st.session_state.tactica_cliente}\nFolio: {st.session_state.tactica_id}\nEquipo: {st.session_state.tactica_equipo}\nValor: {st.session_state.tactica_monto}")
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

                        st.download_button("💾 Descargar Estrategia Completa (.docx)", data=exportar_todo(), file_name=f"Estrategia_{st.session_state.tactica_id}.docx", use_container_width=True)
    except Exception as e:
        st.error(f"Error procesando CSV: {e}")
else:
    with tab_dashboards: st.warning("Sube el archivo CSV del CRM SCOTT en la barra lateral para ver tus datos.")
    with tab_enablement: st.warning("Requiere datos.")
    with tab_scott: st.warning("Requiere datos.")
