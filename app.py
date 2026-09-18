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
        # --- LECTOR ROBUSTO AUTOMÁTICO (Comas o Puntos y Comas) ---
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1', sep=None, engine='python')
        
        # SANEAMIENTO PROFUNDO DE CABECERAS (Quita BOM \ufeff y espacios extra)
        df_raw.columns = [str(c).upper().replace('\ufeff', '').strip() for c in df_raw.columns]
        
        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                if clave in df_raw.columns:
                    return df_raw[clave].copy()
            return pd.Series([None] * len(df_raw))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Cotizacion'] = buscar_col(["COTIZACION"])
        df_clean['Area'] = buscar_col(["AREA"]) 
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA"]) 
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        # Validación de seguridad: si no encuentra la columna clave, detiene y avisa.
        if df_clean['ID_Proyecto'].isna().all():
            st.error("Error de lectura: Asegúrate de guardar el archivo de SCOTT estrictamente como 'CSV (delimitado por comas)'.")
            st.stop()

        df_clean['ID_Proyecto'] = df_clean['ID_Proyecto'].ffill()
        df_clean = df_clean.dropna(subset=['ID_Proyecto'])

        def sanear_y_limpiar(texto):
            if pd.isna(texto): return ""
            t = str(texto)
            t = t.replace("?", "ó").replace("", "í").replace("  ", " ")
            return re.sub(r'\s+', ' ', t).strip().title()

        for col in ['Cliente', 'Descripcion', 'Area', 'Estatus', 'Etapa']:
            df_clean[col] = df_clean[col].apply(sanear_y_limpiar)

        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(lambda x: x.replace("", np.nan).ffill().bfill())

        def extraer_numero(val_str):
            try: return float(''.join(c for c in str(val_str).upper() if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn, monto_usd = pd.Series([0.0]*len(df_raw)), pd.Series([0.0]*len(df_raw))
        if "VALOR" in df_raw.columns:
            monto_mxn = df_raw["VALOR"].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
            monto_usd = df_raw["VALOR"].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
        
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
            
            col_sel1, col_sel2 = st.columns([1, 3])
            with col_sel1:
                moneda_sel = st.selectbox("Seleccionar Moneda para Gráficos:", ["USD ($)", "MXN ($)"])
            
            col_val = 'Monto_USD' if moneda_sel == "USD ($)" else 'Monto_MXN'
            simbolo_moneda = '$,.2f'
            
            st.divider()
            
            st.markdown(f"#### Forecast por Área Oficial ({moneda_sel})")
            df_areas = df.groupby('Area')[col_val].sum().reset_index()
            df_areas = df_areas[df_areas[col_val] > 0] 
            
            grafico_areas = alt.Chart(df_areas).mark_bar(color='#003a70').encode(
                x=alt.X(col_val, title=f'Valor {moneda_sel}'),
                y=alt.Y('Area', sort='-x', title='Área Oficial', axis=alt.Axis(labelLimit=0)),
                tooltip=['Area', alt.Tooltip(col_val, format=simbolo_moneda)]
            ).properties(height=450)
            st.altair_chart(grafico_areas, use_container_width=True)

            st.divider()

            st.markdown(f"#### Salud del Embudo por Fase ({moneda_sel})")
            df_graf_fases = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
            df_graf_fases = df_graf_fases[df_graf_fases[col_val] > 0]
            
            grafico_barras = alt.Chart(df_graf_fases).mark_bar(color='#2ecc71').encode(
                x=alt.X(col_val, title=f'Valor {moneda_sel}'),
                y=alt.Y('Fase_Pipeline', sort='-x', title='Etapa CRM', axis=alt.Axis(labelLimit=0)),
                tooltip=['Fase_Pipeline', alt.Tooltip(col_val, format=simbolo_moneda)]
            ).properties(height=400)
            st.altair_chart(grafico_barras, use_container_width=True)
            
            st.divider()

            st.markdown(f"#### Composición por Pilar Estratégico ({moneda_sel})")
            df_graf_pilares = df.groupby('Pilar_Estrategico')[col_val].sum().reset_index()
            df_graf_pilares = df_graf_pilares[df_graf_pilares[col_val] > 0]
            
            grafico_pastel = alt.Chart(df_graf_pilares).mark_arc(innerRadius=80).encode(
                theta=alt.Theta(field=col_val, type="quantitative"),
                color=alt.Color(field="Pilar_Estrategico", type="nominal", legend=alt.Legend(title="Pilares MESS", orient="bottom", labelLimit=0)),
                tooltip=['Pilar_Estrategico', alt.Tooltip(col_val, format=simbolo_moneda)]
            ).properties(height=450)
            st.altair_chart(grafico_pastel, use_container_width=True)

            st.divider()
            
            st.markdown(f"#### Forecast por Marcas / Fabricantes ({moneda_sel})")
            df_marcas = df[df['Marca_Detectada'] != "Multimarca / No Especificada"].groupby('Marca_Detectada')[col_val].sum().reset_index()
            df_marcas = df_marcas[df_marcas[col_val] > 0]
            
            if not df_marcas.empty:
                grafico_marcas = alt.Chart(df_marcas).mark_bar(color='#e67e22').encode(
                    x=alt.X(col_val, title=f'Valor {moneda_sel}'),
                    y=alt.Y('Marca_Detectada', sort='-x', title='Marca', axis=alt.Axis(labelLimit=0)),
                    tooltip=['Marca_Detectada', alt.Tooltip(col_val, format=simbolo_moneda)]
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
                        st.write(f"Días inactivo: **{row['Días_Activo']:.0f}** | Valor en riesgo: **${row['Monto_USD']:,.2f} USD / ${row['Monto_MXN']:,.2f} MXN**")
                        
                        if st.button(f"Enviar a Laboratorio SCOTT", key=f"btn_scott_{row['ID_Proyecto']}"):
                            st.session_state.proyecto_foco = str(row['ID_Proyecto'])
                            st.success("Proyecto enviado con éxito. Abre la Pestaña 3 para formular la estrategia.")
            else:
                st.success("No hay proyectos estancados detectados. Embudo limpio.")
                
            st.divider()
            st.markdown("#### Base de Datos (Auditoría Rápida)")
            
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
        # TAB 3: LABORATORIO TÁCTICO SCOTT (IA EXPERTA MESS)
        # ==========================================
        with tab_scott:
            st.markdown("### Laboratorio Táctico y Copiloto Comercial MESS")
            st.caption("Selecciona tu proyecto y define la audiencia para generar mensajes de WhatsApp, correos y argumentos técnicos orientados al cierre.")
            
            opciones_proyectos = df.apply(lambda x: f"[{x['ID_Proyecto']}] {x['Cliente']} - {str(x['Descripcion'])[:60]}...", axis=1).tolist()
            opciones_proyectos.insert(0, "-- Selecciona un proyecto clave --")
            
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
                st.markdown("#### Configuración de Interlocutor y Contexto")
                
                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    interlocutor = st.selectbox("Audiencia Destino:", [
                        "Ingeniero de Área / Metrólogo / Mantenimiento / Calidad",
                        "Comprador / Finanzas / Sourcing / Cuentas por Pagar"
                    ])
                with col_l2:
                    area_planta = st.selectbox("Área del Cliente Interesada:", [
                        "Metrología / Control de Calidad",
                        "Mantenimiento / Instalaciones",
                        "Laboratorio de Pruebas / Metalografía",
                        "Proyectos de Manufactura / Producción",
                        "Compras / Abastecimiento"
                    ])
                
                contexto_manual = st.text_area("Detalles tácticos de la interacción (Opcional):", placeholder="Ej. El cliente duda del tiempo de entrega o presiona por descuento en la calibración/equipo...")
                
                st.divider()
                
                if gemini_activo:
                    if st.button("Generar Material de Cierre (WhatsApp, Correo, Llamada y Nota SCOTT)"):
                        with st.spinner("Conectando con el ADN técnico de MESS y formulando estrategia..."):
                            try:
                                model = genai.GenerativeModel("gemini-3.6-flash")
                                
                                prompt_maestro = f"""
                                Eres un experto en Revenue Operations, ventas B2B industriales y especialista senior de MESS Servicios Metrológicos (www.mess.com.mx).
                                MESS ofrece servicios de calibración bajo norma ISO/IEC 17025 (acreditaciones EMA), metrología dimensional, calibración en sitio, y distribución/representación de marcas de alta gama (Fluke, Buehler, Wilson, Baty, Mitutoyo, etc.).
                                
                                Contexto del Proyecto Activo:
                                - Cliente: {datos_proy['Cliente']}
                                - ID Proyecto: {datos_proy['ID_Proyecto']}
                                - Descripción del Equipo/Servicio: {datos_proy['Descripcion']}
                                - Cotizaciones: {datos_proy['Cotizacion']}
                                - Pilar: {datos_proy['Pilar_Estrategico']}
                                - Monto: ${datos_proy['Monto_USD']:,.2f} USD / ${datos_proy['Monto_MXN']:,.2f} MXN
                                
                                Parámetros de la Interacción:
                                - Audiencia destino: {interlocutor}
                                - Área específica de la planta cliente: {area_planta}
                                - Notas / Situación actual del deal: {contexto_manual}
                                
                                INSTRUCCIÓN ESTRICTA:
                                Genera una respuesta estructurada con las siguientes secciones exactas, utilizando un tono comercial impecable y ajustado a la audiencia seleccionada (si es ingeniero, háblale de tablas CMC, trazabilidad, marcas y precisión; si es comprador, háblale de TCO, cumplimiento normativo, tiempos y soporte local en Querétaro):
                                
                                1. ESTRATEGIA Y CONSEJOS TÁCTICOS (2 o 3 puntos clave para asegurar el cierre).
                                2. MENSAJE DE WHATSAPP (Ágil, directo, persuasivo, listo para enviar desde el celular).
                                3. CORREO EJECUTIVO (Formal, enfocado en valor, acreditaciones MESS y llamada a la acción).
                                4. GUION DE LLAMADA Y MANEJO DE OBJECIONES (Preguntas SPIN y cómo responder a bloqueos comunes).
                                5. == TEXTO LISTO PARA PEGAR EN SCOTT == (Nota resumida y profesional de la actividad comercial realizada, incluyendo folios, equipos y siguiente paso estratégico).
                                """
                                
                                response = model.generate_content(prompt_maestro)
                                st.success("Material táctico generado con éxito.")
                                st.write(response.text)
                            except Exception as e:
                                st.error(f"Error de conexión con la API de Gemini: {e}")
                else:
                    st.warning("Agrega tu clave gemini_api_key en los Secrets para activar el Laboratorio Táctico.")

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
else:
    st.info("Sube el reporte comercial formato CSV (Plantilla Radar) para iniciar tu cuarto de estrategia.")
