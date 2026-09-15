import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import google.generativeai as genai

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# CONFIGURACIÓN GEMINI API (3.6 FLASH)
# ==========================================
if "gemini_api_key" in st.secrets:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    gemini_activo = True
else:
    gemini_activo = False

# ==========================================
# MEMORIA DE SESIÓN (SINERGIA ENABLEMENT -> SCOTT)
# ==========================================
if 'proyecto_foco' not in st.session_state:
    st.session_state.proyecto_foco = None

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
    .stDataFrame { font-size: 14px !important; }
    .ficha-scott { background-color: #f4f6f7; padding: 20px; border-radius: 8px; border: 1px solid #d5d8dc; margin-bottom: 20px; }
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
st.markdown('<div class="subtitulo">Módulo Coadyuvante CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir extracción CRM (CSV)", type=["csv"])

if archivo_cargado is not None:
    try:
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        
        # --- PROCESAMIENTO Y LIMPIEZA ---
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
            return re.sub(r'\s+', ' ', str(texto).replace("?", " ")).strip().title()

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
        df = df[df['Estatus'].str.contains('PROCESO|PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)].copy()
        
        # ==========================================
        # CLASIFICACIÓN (PILARES Y MARCAS)
        # ==========================================
        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            if any(k in texto for k in ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "BRAZO", "ZEISS", "BATY"]):
                return "1. Alta Gama (Servicios Especiales)"
            elif any(k in texto for k in ["CALIBRACIÓN", "CALIBRACION", "LABORATORIO", "DIMENSIONAL", "PRENSA"]):
                return "2. Calibraciones (Comunes)"
            else:
                return "3. Productos (Equipos y Consumibles)"
        
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
        filtro_pilar = st.sidebar.multiselect("Filtrar por Pilar de Negocio:", df['Pilar_Estrategico'].unique(), default=df['Pilar_Estrategico'].unique())
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
        tab_dashboards, tab_enablement, tab_scott = st.tabs([
            "1. Dashboards Directivos (Inteligencia Financiera)", 
            "2. Enablement (Cuellos de Botella)", 
            "3. Laboratorio Táctico SCOTT (Estrategia AI)"
        ])

        # ==========================================
        # TAB 1: DASHBOARDS DIRECTIVOS
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
            
            # GRÁFICOS GRANDES EN BLOQUES INDIVIDUALES
            
            st.markdown("#### Forecast por Área (Basado en la plantilla de SCOTT)")
            df_areas = df.groupby('Area')['Monto_USD'].sum().reset_index()
            grafico_areas = alt.Chart(df_areas).mark_bar(color='#003a70').encode(
                x=alt.X('Monto_USD', title='Valor USD ($)'),
                y=alt.Y('Area', sort='-x', title='Área Oficial'),
                tooltip=['Area', alt.Tooltip('Monto_USD', format='$,.2f')]
            ).properties(height=450)
            st.altair_chart(grafico_areas, use_container_width=True)

            st.divider()

            st.markdown("#### Salud del Embudo por Fase")
            df_graf_fases = df.groupby('Fase_Pipeline')['Monto_USD'].sum().reset_index()
            grafico_barras = alt.Chart(df_graf_fases).mark_bar(color='#2ecc71').encode(
                x=alt.X('Fase_Pipeline', title='Etapa CRM'),
                y=alt.Y('Monto_USD', title='Valor USD ($)'),
                tooltip=['Fase_Pipeline', alt.Tooltip('Monto_USD', format='$,.2f')]
            ).properties(height=450)
            st.altair_chart(grafico_barras, use_container_width=True)
            
            st.divider()

            st.markdown("#### Composición por Pilar Estratégico")
            df_graf_pilares = df.groupby('Pilar_Estrategico')['Monto_USD'].sum().reset_index()
            grafico_pastel = alt.Chart(df_graf_pilares).mark_arc(innerRadius=80).encode(
                theta=alt.Theta(field="Monto_USD", type="quantitative"),
                color=alt.Color(field="Pilar_Estrategico", type="nominal", legend=alt.Legend(title="Pilares MESS", orient="bottom")),
                tooltip=['Pilar_Estrategico', alt.Tooltip('Monto_USD', format='$,.2f')]
            ).properties(height=450)
            st.altair_chart(grafico_pastel, use_container_width=True)

            st.divider()
            
            st.markdown("#### Forecast por Marcas / Fabricantes")
            df_marcas = df[df['Marca_Detectada'] != "Multimarca / No Especificada"].groupby('Marca_Detectada')['Monto_USD'].sum().reset_index()
            if not df_marcas.empty:
                grafico_marcas = alt.Chart(df_marcas).mark_bar(color='#e67e22').encode(
                    x=alt.X('Monto_USD', title='Valor USD ($)'),
                    y=alt.Y('Marca_Detectada', sort='-x', title='Marca'),
                    tooltip=['Marca_Detectada', alt.Tooltip('Monto_USD', format='$,.2f')]
                ).properties(height=450)
                st.altair_chart(grafico_marcas, use_container_width=True)
            else:
                st.info("No se detectaron proyectos de marcas específicas en el pipeline activo.")

        # ==========================================
        # TAB 2: ENABLEMENT
        # ==========================================
        with tab_enablement:
            st.markdown("### Riesgo Operativo y Proyectos Estancados")
            st.caption("Proyectos que requieren apalancamiento estratégico o descarte inmediato.")
            
            estancados = df[(df['Fase_Pipeline'].isin(['1. Propuesta', '2. Cotización'])) & (df['Días_Activo'] > 15)].sort_values(by='Monto_USD', ascending=False)
            if not estancados.empty:
                for _, row in estancados.head(4).iterrows():
                    with st.container(border=True):
                        st.markdown(f"**PROYECTO ESTANCADO: {row['ID_Proyecto']} | {row['Cliente']}**")
                        st.write(f"**Equipo/Servicio:** {row['Descripcion']}")
                        st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Valor en riesgo: **${row['Monto_USD']:,.2f} USD**")
                        
                        # BOTÓN DE SINERGIA CON SCOTT
                        if st.button(f"Enviar a Laboratorio SCOTT", key=f"btn_scott_{row['ID_Proyecto']}"):
                            st.session_state.proyecto_foco = str(row['ID_Proyecto'])
                            st.success("Proyecto enviado con éxito. Abre la Pestaña 3 para formular la estrategia.")
            else:
                st.success("No hay proyectos estancados detectados. Embudo limpio.")
                
            st.divider()
            st.markdown("#### Base de Datos (Auditoría Rápida)")
            
            # CONFIGURACIÓN PARA QUE LAS COLUMNAS SE AJUSTEN SIN SCROLL HORIZONTAL EXCESIVO
            st.dataframe(
                df[['ID_Proyecto', 'Cliente', 'Descripcion', 'Cotizacion', 'Fase_Pipeline', 'Monto_USD']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID_Proyecto": st.column_config.TextColumn("ID", width="small"),
                    "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
                    "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
                    "Cotizacion": st.column_config.TextColumn("Folio(s)", width="small"),
                    "Fase_Pipeline": st.column_config.TextColumn("Fase", width="small"),
                    "Monto_USD": st.column_config.NumberColumn("USD", format="$%.2f", width="small")
                }
            )

        # ==========================================
        # TAB 3: LABORATORIO TÁCTICO SCOTT (IA + MEDDPICC)
        # ==========================================
        with tab_scott:
            st.markdown("### Enlace Estratégico CRM (Radar a SCOTT)")
            st.caption("Selecciona una cuenta clave para estructurar la estrategia antes de capturar tu actividad en SCOTT.")
            
            opciones_proyectos = df.apply(lambda x: f"[{x['ID_Proyecto']}] {x['Cliente']} - {str(x['Descripcion'])[:60]}...", axis=1).tolist()
            opciones_proyectos.insert(0, "-- Selecciona un proyecto clave --")
            
            # LÓGICA DE SINERGIA: Seleccionar automáticamente si viene de Enablement
            index_default = 0
            if st.session_state.proyecto_foco:
                for i, opcion in enumerate(opciones_proyectos):
                    if f"[{st.session_state.proyecto_foco}]" in opcion:
                        index_default = i
                        break
            
            seleccion = st.selectbox("Seleccionar Proyecto Objetivo:", opciones_proyectos, index=index_default)
            
            if seleccion != "-- Selecciona un proyecto clave --":
                id_seleccionado = seleccion.split("]")[0].replace("[", "")
                datos_proy = df[df['ID_Proyecto'].astype(str) == id_seleccionado].iloc[0]
                
                st.markdown(f"""
                <div class="ficha-scott">
                    <h4>FICHA DE PROYECTO PARA SCOTT</h4>
                    <b>Cliente/Planta:</b> {datos_proy['Cliente']}<br>
                    <b>Proyecto ID:</b> {datos_proy['ID_Proyecto']}<br>
                    <b>Descripción / Equipo:</b> <span style='color:#003a70; font-weight:bold;'>{datos_proy['Descripcion']}</span><br>
                    <b>Cotizaciones Vinculadas:</b> <span style='color:red; font-weight:bold;'>{datos_proy['Cotizacion']}</span><br>
                    <b>Pilar y Fase:</b> {datos_proy['Pilar_Estrategico']} | {datos_proy['Fase_Pipeline']}<br>
                    <b>Monto:</b> ${datos_proy['Monto_USD']:,.2f} USD / ${datos_proy['Monto_MXN']:,.2f} MXN
                </div>
                """, unsafe_allow_html=True)
                
                st.divider()
                st.markdown("#### 1. Calificación MEDDPICC (Validación interna)")
                c1, c2, c3 = st.columns(3)
                eb = c1.selectbox("Economic Buyer", ["Pendiente", "Mapeado", "Acceso Directo Validado"])
                dc = c2.selectbox("Decision Criteria", ["Precio", "Aspecto Técnico", "Tiempos", "Post Venta"])
                ch = c3.selectbox("Champion", ["Ninguno", "Usuario Técnico", "Gerencia Aliada"])
                pain = st.text_input("Describe el Pain (Dolor/Problema de negocio del cliente):")
                
                st.divider()
                st.markdown("#### 2. Copiloto AI (Generador de Notas SCOTT)")
                
                if gemini_activo:
                    prompt_usuario = st.text_area("¿Cuál es el objetivo táctico de esta interacción?", placeholder="Ej. Voy a visitar la planta para validar el presupuesto con el gerente o redactar un correo empujando la orden de compra...")
                    
                    if st.button("Generar Estrategia y Nota para SCOTT"):
                        with st.spinner("Procesando inteligencia comercial para CRM..."):
                            try:
                                model = genai.GenerativeModel("gemini-3.6-flash")
                                
                                prompt_maestro = f"""
                                Eres un experto en Revenue Operations, ventas B2B y metodologías SPIN y MEDDPICC.
                                El estratega de ventas industriales de MESS Servicios Metrológicos necesita documentar una interacción en el CRM "SCOTT".
                                
                                Contexto del Proyecto:
                                - Cliente: {datos_proy['Cliente']}
                                - ID Proyecto: {datos_proy['ID_Proyecto']}
                                - Descripción del Equipo/Servicio: {datos_proy['Descripcion']}
                                - Cotizaciones: {datos_proy['Cotizacion']}
                                - Pilar: {datos_proy['Pilar_Estrategico']}
                                - Pain del cliente: {pain}
                                
                                Requerimiento del usuario: {prompt_usuario}
                                
                                INSTRUCCIÓN:
                                1. Primero, dale 2 o 3 consejos tácticos de cómo manejar esta objeción/visita usando preguntas SPIN enfocadas en el equipo/servicio específico que se está cotizando.
                                2. Al final, genera un bloque de texto que diga "== TEXTO LISTO PARA PEGAR EN SCOTT ==". Este bloque debe estar formateado profesionalmente para pegarse como una nota de actividad en el CRM, incluyendo los datos del folio de cotización, el equipo, el objetivo y el siguiente paso estratégico.
                                """
                                
                                response = model.generate_content(prompt_maestro)
                                st.success("Estrategia y Nota SCOTT generadas con éxito.")
                                st.write(response.text)
                            except Exception as e:
                                st.error(f"Error de conexión con la API de Gemini: {e}")
                else:
                    st.warning("Agrega tu clave gemini_api_key en los Secrets para activar el Laboratorio Táctico.")

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
else:
    st.info("Sube el reporte comercial formato CSV (Plantilla Radar) para iniciar tu cuarto de estrategia.")
