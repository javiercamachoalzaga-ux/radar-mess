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
# CONFIGURACIÓN GEMINI API (CON SEGURIDAD APAGADA)
# ==========================================
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

# ==========================================
# MEMORIA DE SESIÓN (STATE) PARA TABS DE IA
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
    .ficha-scott { background-color: #f4f6f7; padding: 20px; border-radius: 8px; border: 1px solid #d5d8dc; margin-bottom: 20px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# SIMULACIÓN DE DATOS MEDDPICC (MÓDULO 4)
# ==========================================
def generar_datos_meddpicc():
    data = {
        'Oportunidad': [
            'CMM Mitutoyo Crysta-Apex - Ford', 
            'Scantech SimScan - Fulltech', 
            'Brazo Faro / Servicios - Tremec', 
            'Calibración Dimensional Anual - Dana', 
            'Zeiss Contura (Competencia) - BRP'
        ],
        'Valor_USD': [85000, 32842, 45000, 8500, 120000],
        'Etapa_Pipeline': [3, 4, 2, 5, 1],
        'M': [1, 2, 0, 2, 0],
        'E': [2, 1, 1, 2, 0],
        'D1': [1, 2, 1, 2, 1],
        'D2': [1, 2, 0, 2, 0],
        'P': [2, 2, 1, 2, 1],
        'I': [1, 1, 0, 2, 0],
        'C1': [2, 2, 1, 2, 0],
        'C2': [1, 2, 0, 2, 1]
    }
    df_m = pd.DataFrame(data)
    df_m['Health_Score'] = df_m[['M','E','D1','D2','P','I','C1','C2']].sum(axis=1)
    
    # Semaforización
    condiciones = [
        (df_m['Health_Score'] < 8),
        (df_m['Health_Score'] >= 8) & (df_m['Health_Score'] <= 12),
        (df_m['Health_Score'] > 12)
    ]
    valores = ['Riesgo Alto', 'Precaución', 'Saludable']
    df_m['Estado'] = np.select(condiciones, valores)
    return df_m

df_meddpicc = generar_datos_meddpicc()

st.markdown('<div class="titulo-radar">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Módulo CRM SCOTT & Auditoría MEDDPICC | Revenue Operations</div>', unsafe_allow_html=True)

# ==========================================
# TABS PRINCIPALES
# ==========================================
tab_dashboards, tab_enablement, tab_scott, tab_meddpicc = st.tabs([
    "1. Dashboards CRM", 
    "2. Proyectos Estancados", 
    "3. Laboratorio IA (360°)",
    "4. Dashboard MEDDPICC"
])

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV) para Tabs 1, 2 y 3", type=["csv"])

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
                
        if header_idx != -1:
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
            
            def clasificar_fase(etapa):
                e = str(etapa).upper()
                if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
                elif 'NEGOCIACI' in e: return "3. Negociación"
                elif 'COTIZACI' in e: return "2. Cotización"
                elif 'PROPUESTA' in e: return "1. Propuesta"
                else: return "5. En Proceso"
            
            df['Fase_Pipeline'] = df['Etapa'].apply(clasificar_fase)
            df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
            df['Días_Activo'] = (pd.Timestamp.now() - df['Fecha_Creacion_DT']).dt.days

            # --- RENDERIZADO TABS 1 Y 2 ---
            with tab_dashboards:
                st.info("Visualización CRM cargada. Tu Pareto y embudo están listos (Código minimizado por limpieza).")
                st.dataframe(df.head(5))

            with tab_enablement:
                st.markdown("### Riesgo Operativo y Proyectos Estancados")
                estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Monto_USD', ascending=False)
                if not estancados.empty:
                    for _, row in estancados.head(4).iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{row['ID_Proyecto']} | {row['Cliente']}**")
                            st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Riesgo: **${row['Monto_USD']:,.2f} USD**")
                            if st.button(f"Analizar en Laboratorio", key=f"btn_{row['ID_Proyecto']}"):
                                st.session_state.proyecto_foco = str(row['ID_Proyecto'])
                                st.success("Proyecto enviado. Abre la Pestaña 3.")
                else:
                    st.success("Embudo limpio.")

            # ==========================================
            # TAB 3: LABORATORIO TÁCTICO (NUEVA VISIÓN 360°)
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
                    
                    # SIN BOTONES, SOLO CONTEXTO DIRECTO
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
                                    Separa tu respuesta usando ESTOS EXACTOS MARCADORES. No uses negritas ni Markdown en los marcadores.

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
                                    
                                    # Extracción Múltiple Robusta
                                    extracciones = {}
                                    secciones = ['ANALISIS', 'WHATSAPP', 'CORREO', 'LLAMADA', 'MARKETING', 'BITACORA']
                                    
                                    for i, sec in enumerate(secciones):
                                        inicio = f"SECCION_{sec}:"
                                        fin = f"SECCION_{secciones[i+1]}:" if i+1 < len(secciones) else "$"
                                        patron = f"{inicio}(.*?)(?={fin})"
                                        match = re.search(patron, texto_raw, re.DOTALL | re.IGNORECASE)
                                        extracciones[sec] = match.group(1).strip() if match else "Error de formato."

                                    st.session_state.tactica_analisis = extracciones['ANALISIS']
                                    st.session_state.tactica_whatsapp = extracciones['WHATSAPP']
                                    st.session_state.tactica_correo = extracciones['CORREO']
                                    st.session_state.tactica_llamada = extracciones['LLAMADA']
                                    st.session_state.tactica_marketing = extracciones['MARKETING']
                                    st.session_state.tactica_bitacora = extracciones['BITACORA']
                                    
                                    st.session_state.tactica_cliente = datos_proy['Cliente']
                                    st.session_state.tactica_id = datos_proy['ID_Proyecto']
                                    st.session_state.tactica_equipo = datos_proy['Descripcion']
                                    st.session_state.tactica_monto = f"${datos_proy['Monto_USD']:,.2f} USD"
                                    
                                except Exception as e:
                                    st.error(f"Error de IA: {e}")

                    # VISTA SIMULTÁNEA
                    if st.session_state.tactica_whatsapp:
                        st.success("Arsenal táctico generado con éxito.")
                        
                        colA, colB = st.columns(2)
                        with colA:
                            st.markdown("#### 🧠 Análisis MEDDPICC / SPIN")
                            st.info(st.session_state.tactica_analisis)
                            
                            st.markdown("#### 📲 Mensaje WhatsApp")
                            st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_whatsapp}</div>", unsafe_allow_html=True)
                            
                            st.markdown("#### 📞 Guion Llamada")
                            st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_llamada}</div>", unsafe_allow_html=True)

                        with colB:
                            st.markdown("#### ✉️ Correo Electrónico")
                            st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_correo}</div>", unsafe_allow_html=True)
                            
                            st.markdown("#### 🎯 Solicitud Marketing (ABM)")
                            st.warning(st.session_state.tactica_marketing)
                            
                            st.markdown("#### 📋 Bitácora CRM (SCOTT)")
                            st.success(st.session_state.tactica_bitacora)
                            
                        # BOTONERA DE EXPORTACIÓN (Sin cambiar lógica compleja de Word)
                        if docx_disponible:
                            st.divider()
                            st.markdown("### 📤 Central de Exportación")
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
# TAB 4: MÓDULO MEDDPICC (PLOTLY DASHBOARD)
# ==========================================
with tab_meddpicc:
    st.markdown("### Auditoría de Calificación B2B (Framework MEDDPICC)")
    st.caption("Evalúa la madurez de calificación cruzando las etapas del embudo con el Health Score del proyecto.")
    
    # Filtros para el Dashboard
    col_f1, col_f2 = st.columns(2)
    with col_f1: 
        fases_disp = df_meddpicc['Etapa_Pipeline'].unique()
        filtro_etapa = st.multiselect("Filtrar por Etapa de Pipeline:", sorted(fases_disp), default=sorted(fases_disp))
    with col_f2: 
        score_min = st.slider("Health Score Mínimo (Suma MEDDPICC):", 0, 16, 0)
        
    # Aplicar filtros
    df_filtrado = df_meddpicc[(df_meddpicc['Etapa_Pipeline'].isin(filtro_etapa)) & (df_meddpicc['Health_Score'] >= score_min)]
    
    # KPIs Top
    if not df_filtrado.empty:
        val_total = df_filtrado['Valor_USD'].sum()
        avg_score = df_filtrado['Health_Score'].mean()
        riesgos = df_filtrado[(df_filtrado['Etapa_Pipeline'] >= 4) & (df_filtrado['Health_Score'] < 10)].shape[0]
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Valor Total del Pipeline (Filtro)", f"${val_total:,.0f} USD")
        k2.metric("Promedio Health Score", f"{avg_score:.1f} / 16")
        k3.metric("Oportunidades en Riesgo Crítico", f"{riesgos} cuentas", "Etapa Avanzada + Score Bajo")
        
        st.divider()
        
        # Gráfico 1: Scatter Plot Plotly
        st.markdown("#### Matriz de Dispersión: Madurez vs. Riesgo")
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
        # Añadir cuadrícula roja visual para zona de peligro
        fig_scatter.add_hrect(y0=0, y1=8, line_width=0, fillcolor="red", opacity=0.05)
        fig_scatter.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        st.divider()
        
        # Gráfico 2: Heatmap de Brechas MEDDPICC
        st.markdown("#### Matriz de Calor (Puntos Ciegos MEDDPICC)")
        st.caption("0: Desconocido (Rojo) | 1: Identificado (Amarillo) | 2: Validado (Verde)")
        
        # Preparar data para Heatmap
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
