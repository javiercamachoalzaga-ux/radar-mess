import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re
import google.generativeai as genai

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

# ==========================================
# CONFIGURACIÓN GEMINI API
# ==========================================
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

# ==========================================
# INICIALIZACIÓN DE MEMORIA (AGENDA Y CARRITO)
# ==========================================
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=[
        'ID_Tarea', 'Fecha', 'Cliente', 'ID_Proyecto', 'Cotizacion', 
        'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN', 'Tipo_Accion', 'Descripcion', 'Completado'
    ])
if 'clear_key' not in st.session_state: st.session_state.clear_key = 0
if 'carrito' not in st.session_state: st.session_state.carrito = set()

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo-radar { font-size: 42px; font-weight: 900; color: #003a70; margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 16px; color: #555555; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #7f8c8d !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important; }
    [data-testid="stSidebar"] { background-color: #f4f6f7 !important; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] * { color: #003a70 !important; font-weight: 600; }
    .stDataFrame { font-size: 14px !important; }
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

st.markdown('<div class="titulo-radar">Radar Comercial y Enablement B2B</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Gestión Estratégica, Metodología de Cierre y Copiloto AI</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto", type=["csv"])

if archivo_cargado is not None:
    try:
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        
        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    if str(col).upper().strip() == clave or str(col).upper().strip() == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

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

        df_clean['ID_Proyecto'] = df_clean['ID_Proyecto'].ffill()
        df_clean = df_clean.dropna(subset=['ID_Proyecto'])

        def limpiar_ortografia(texto):
            if pd.isna(texto): return ""
            texto = re.sub(r'\s+', ' ', str(texto).replace("?", " ")).strip()
            return texto.title()

        for col in ['Cliente', 'Descripcion', 'Area', 'Estatus', 'Etapa']:
            df_clean[col] = df_clean[col].apply(limpiar_ortografia)

        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        def extraer_numero(val_str):
            try: return float(''.join(c for c in str(val_str).upper() if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn, monto_usd = pd.Series([0.0]*len(df_raw)), pd.Series([0.0]*len(df_raw))
        for col in df_raw.columns:
            if str(col).upper().strip().startswith("VALOR"):
                monto_mxn += df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                monto_usd += df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
        
        df_clean['Monto_MXN'], df_clean['Monto_USD'] = monto_mxn, monto_usd

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
        df = df[df['Estatus'].str.contains('PROCESO|PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)].copy()
        
        df['Unidad_Presupuesto'] = df['Area'].apply(lambda a: "ALTA GAMA" if any(k in str(a).upper() for k in ["ALTA GAMA", "EQUIPO", "CMM", "ZEISS", "SCANNER"]) else ("LABORATORIOS" if any(k in str(a).upper() for k in ["LABORATORIO", "CALIBRACIÓN", "DIMENSIONAL"]) else "PRODUCTOS"))
        
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            else: return "5. En Proceso (Otros)"
        df['Fase_Pipeline'] = df['Etapa'].apply(clasificar_fase)

        df['Peso_Interno_Orden'] = df['Monto_USD'] + (df['Monto_MXN'] / 19.50)
        
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)
        df['Días_Activo'] = (pd.Timestamp.now() - df['Fecha_Creacion_DT']).dt.days

        st.sidebar.divider()
        st.sidebar.header("Filtros Tácticos")
        busqueda_proyecto = st.sidebar.text_input("Buscar ID o Cliente:")
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]

        # ¡AQUÍ ESTÁ LA LÍNEA QUE FALTABA!
        contenedor_agenda_lateral = st.sidebar.container()

        mes_actual, anio_actual = pd.Timestamp.now().month, pd.Timestamp.now().year
        
        tab_analisis, tab_implementacion, tab_ejecucion, tab_ai = st.tabs([
            "1. Inteligencia Financiera (Forecast)", 
            "2. Enablement y Ejecución", 
            "3. Metodología y Agenda",
            "4. Gemini Copilot"
        ])

        # ==========================================
        # 1. FORECAST Y GAP ANALYSIS
        # ==========================================
        with tab_analisis:
            st.markdown("### Análisis de Brecha (Gap Analysis) vs Cuota")
            META_MENSUAL_USD = 80000.00
            
            df_mes = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)]
            usd_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_USD'].sum()
            mxn_caliente = df_mes[df_mes['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO'])]['Monto_MXN'].sum()
            usd_tibio = df_mes[df_mes['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])]['Monto_USD'].sum()
            
            gap_actual_usd = META_MENSUAL_USD - usd_caliente
            
            col_g1, col_g2, col_g3 = st.columns(3)
            col_g1.metric("Meta Comercial del Mes", f"${META_MENSUAL_USD:,.2f} USD")
            col_g2.metric("Pipeline Caliente USD (Cierre Probable)", f"${usd_caliente:,.2f} USD", f"+ ${mxn_caliente:,.2f} MXN Adicionales")
            if gap_actual_usd > 0:
                col_g3.metric("Brecha para llegar a la Meta (GAP)", f"${gap_actual_usd:,.2f} USD", "- Requiere acción inmediata")
                st.warning(f"Estrategia: Tienes ${usd_tibio:,.2f} USD estancados en Propuesta/Cotización. Necesitas acelerar conversiones para cerrar tu GAP de ${gap_actual_usd:,.0f} USD. Los montos en MXN te sirven de bolsa de protección operativa.")
            else:
                col_g3.metric("Brecha (GAP)", "$0.00 USD", "+ Meta Asegurada")
                st.success(f"Pipeline caliente cubre la meta de $80,000 USD. Además traes ${mxn_caliente:,.2f} MXN en el radar para maximizar resultados.")
            
            st.divider()
            st.markdown("### Embudo de Ventas Vivo")
            df_pipeline = df.groupby('Fase_Pipeline').agg(Num_Proyectos=('ID_Proyecto', 'nunique'), Monto_USD=('Monto_USD', 'sum'), Monto_MXN=('Monto_MXN', 'sum')).reset_index()
            cols = st.columns(4)
            for col, fase in zip(cols, ["1. Propuesta", "2. Cotización", "3. Negociación", "4. Esperando PO"]):
                data_fase = df_pipeline[df_pipeline['Fase_Pipeline'] == fase]
                if not data_fase.empty:
                    proy, u, m = data_fase['Num_Proyectos'].iloc[0], data_fase['Monto_USD'].iloc[0], data_fase['Monto_MXN'].iloc[0]
                else:
                    proy, u, m = 0, 0.0, 0.0
                col.metric(fase, f"{proy} Proyectos", f"${u:,.0f} USD | ${m:,.0f} MXN")

        # ==========================================
        # 2. ENABLEMENT Y DISPARADORES DE MARKETING
        # ==========================================
        def render_table_interactiva(df_subset, sufijo_clave):
            if df_subset.empty: return st.info("Sin proyectos.")
            df_mostrar = df_subset[['ID_Proyecto', 'Cliente', 'Fase_Pipeline', 'Monto_USD', 'Monto_MXN']].copy()
            df_mostrar.insert(0, 'Seleccionar', df_mostrar['ID_Proyecto'].apply(lambda x: x in st.session_state.carrito))
            df_editado = st.data_editor(df_mostrar, hide_index=True, use_container_width=True, key=f"tbl_{sufijo_clave}_{st.session_state.clear_key}", 
                column_config={"Monto_USD": st.column_config.NumberColumn("Valor USD", format="$%.2f"), "Monto_MXN": st.column_config.NumberColumn("Valor MXN", format="$%.2f")})
            st.session_state.carrito = (st.session_state.carrito - set(df_mostrar['ID_Proyecto'])) | set(df_editado[df_editado['Seleccionar']]['ID_Proyecto'])

        with tab_implementacion:
            st.markdown("### Alertas de Marketing y Nurturing B2B")
            st.caption("Proyectos estratégicos estancados que requieren apalancamiento con material de marketing.")
            
            estancados = df[(df['Fase_Pipeline'] == '1. Propuesta') & (df['Días_Activo'] > 15)].copy()
            if not estancados.empty:
                for _, row in estancados.head(3).iterrows():
                    st.error(f"ALERTA: Proyecto {row['ID_Proyecto']} ({row['Cliente']}) lleva {row['Días_Activo']:.0f} días en Propuesta. Valor: ${row['Monto_USD']:,.2f} USD / ${row['Monto_MXN']:,.2f} MXN.")
                    st.markdown("> Acción Sugerida (Marketing): Enviar matriz de ROI técnico o gestionar una invitación VIP al showroom para re-enganchar al tomador de decisión.")
            else:
                st.success("No hay cuellos de botella detectados en la fase de Propuestas.")
                
            st.divider()
            st.markdown("### Centro de Ejecución (Selección de Ruta)")
            render_table_interactiva(df, "global")

        # ==========================================
        # 3. METODOLOGÍA Y AGENDA (MEDDPICC)
        # ==========================================
        with contenedor_agenda_lateral:
            st.header("Encolar Ruta")
            if st.session_state.carrito:
                st.info(f"Proyectos en carrito: {len(st.session_state.carrito)}")
                accion_lote = st.selectbox("Acción a ejecutar:", ["Visita Presencial", "Llamada Consultiva", "Cierre Comercial"])
                fecha_lote = st.date_input("Fecha:", pd.Timestamp.now().date())
                if st.button("Agendar"):
                    for _, row in df[df['ID_Proyecto'].isin(st.session_state.carrito)].iterrows():
                        nueva_tarea = pd.DataFrame([{ 'ID_Tarea': np.random.randint(1, 10000), 'Fecha': fecha_lote, 'Cliente': row['Cliente'], 'ID_Proyecto': row['ID_Proyecto'], 'Cotizacion': row['Cotizacion'], 'Monto_USD': row['Monto_USD'], 'Monto_MXN': row['Monto_MXN'], 'Tipo_Accion': accion_lote, 'Descripcion': row['Descripcion'], 'Completado': False }])
                        st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    st.session_state.carrito = set(); st.session_state.clear_key += 1; st.rerun()

        with tab_ejecucion:
            st.markdown("### Tablero de Gestión y Metodología Comercial")
            fecha_vista = st.date_input("Seleccionar día a visualizar:", pd.Timestamp.now().date())
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            
            if not df_dia.empty:
                df_dia_show = df_dia[['Completado', 'Cliente', 'ID_Proyecto', 'Tipo_Accion']].copy()
                st.data_editor(df_dia_show, hide_index=True, use_container_width=True, key="ed_agenda")
                st.divider()
                
                st.markdown("### Calificación de Oportunidad (Framework MEDDPICC)")
                st.caption("Obligatorio para perfilar el cierre de cuentas estratégicas.")
                cliente_memo = st.selectbox("Selecciona la cuenta a calificar:", df_dia['Cliente'].unique())
                
                if cliente_memo:
                    col_m1, col_m2 = st.columns(2)
                    col_m1.selectbox("Economic Buyer (Comprador Económico)", ["No identificado", "Mapeado pero sin acceso", "Acceso directo y validado"])
                    col_m1.selectbox("Decision Criteria (Criterio de Decisión)", ["Precio", "Tiempo de Entrega", "Especificación Técnica (Precisión)", "Soporte Post-Venta"])
                    col_m2.text_input("Identificar el Pain (Dolor o problema principal del cliente)")
                    col_m2.selectbox("Champion (Campeón Interno)", ["Sin campeón", "Ingeniero/Técnico aliado", "Gerente impulsando la compra"])
                    st.button("Guardar Calificación Estratégica")
            else:
                st.info("Agenda libre. Utiliza el Centro de Ejecución para programar cuentas.")

        # ==========================================
        # 4. COPILOTO GEMINI AI (REVENUE OPS)
        # ==========================================
        with tab_ai:
            st.markdown("### Gemini B2B Sales Copilot")
            st.caption("Tu asistente de inteligencia artificial para redacción persuasiva y análisis de cuentas.")
            
            if gemini_activo:
                prompt = st.text_area("¿En qué te ayudo hoy, estratega?", placeholder="Ej. Redacta un correo corto bajo la metodología SPIN para un cliente que necesita calibrar su brazo articulado...")
                if st.button("Generar con IA"):
                    with st.spinner("Procesando inteligencia comercial..."):
                        try:
                            model = genai.GenerativeModel("gemini-1.5-pro-latest")
                            instruccion = "Eres un experto en ventas B2B y Revenue Operations. Responde de manera profesional, directa y orientada a cerrar ventas industriales en México. " + prompt
                            response = model.generate_content(instruccion)
                            st.write(response.text)
                        except Exception as e:
                            st.error(f"Error de conexión con la API de Gemini: {e}")
            else:
                st.warning("La API Key de Gemini no está configurada.")
                st.markdown("Para activar el Copiloto, agrega tu clave en los Secrets de Streamlit bajo el nombre `gemini_api_key`.")

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
else:
    st.info("Sube el reporte comercial formato CSV (Plantilla Radar) para iniciar.")
