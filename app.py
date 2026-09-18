import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime
import re
import google.generativeai as genai
import urllib.parse
import io

# Intenta importar la librería de Word. Si no está instalada, no rompe la app, solo avisa.
try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide", initial_sidebar_state="expanded")

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
if 'proyecto_foco' not in st.session_state:
    st.session_state.proyecto_foco = None
if 'tactica_generada' not in st.session_state:
    st.session_state.tactica_generada = ""
if 'tactica_cliente' not in st.session_state:
    st.session_state.tactica_cliente = ""
if 'tactica_id' not in st.session_state:
    st.session_state.tactica_id = ""

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
                        st.info(f"💡 **Insight Estratégico:** Solo **{num_clientes} cliente(s)** conforman aproximadamente el 80% del valor total de tu pipeline actual. Estos son tus VIPs.")
                
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
                    else:
                        st.info("Sin proyectos de marcas específicas.")

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
        # TAB 3: LABORATORIO TÁCTICO SCOTT (IA EXPERTA)
        # ==========================================
        with tab_scott:
            st.markdown("### Laboratorio Táctico y Copiloto Comercial MESS")
            st.caption("Selecciona tu proyecto y el tipo de operación para diseñar la táctica.")
            
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
                st.markdown("#### Configuración de la Operación Estratégica")
                
                tipo_operacion = st.radio("Tipo de Acción a Ejecutar:", [
                    "Aceleración y Cierre (Generar presión en deals activos)", 
                    "Apertura y Visitas Estratégicas (Prospección y acompañamiento directivo/PM)"
                ])

                col_l1, col_l2 = st.columns(2)
                with col_l1:
                    interlocutor = st.selectbox("Audiencia Destino:", [
                        "Ingeniero de Área / Metrólogo / Mantenimiento / Calidad",
                        "Comprador / Finanzas / Sourcing / Gerente de Planta"
                    ])
                with col_l2:
                    area_planta = st.selectbox("Área del Cliente Interesada:", [
                        "Metrología / Control de Calidad",
                        "Mantenimiento / Instalaciones",
                        "Laboratorio de Pruebas / Metalografía",
                        "Proyectos de Manufactura / Producción",
                        "Compras / Abastecimiento"
                    ])
                
                contexto_manual = st.text_area("Detalles tácticos (Ej. El cliente duda del tiempo de entrega, o iré acompañado de Óscar Morales la próxima semana):", placeholder="Escribe el contexto comercial...")
                
                st.divider()
                
                if gemini_activo:
                    boton_texto = "Generar Plan de Visita y Guion de Apertura" if "Apertura" in tipo_operacion else "Generar Material de Cierre (Marketing, Correo, Guion)"
                    
                    if st.button(boton_texto):
                        with st.spinner("Conectando con el ADN técnico y comercial de MESS..."):
                            try:
                                # RESTAURADO A 3.6-FLASH PARA EVITAR CONFLICTOS DE ENTORNO
                                model = genai.GenerativeModel("gemini-3.6-flash")
                                
                                if "Apertura" in tipo_operacion:
                                    prompt_maestro = f"""
                                    Eres un experto en Revenue Operations, ventas B2B industriales, y especialista senior de MESS Servicios Metrológicos. Dominas las metodologías SPIN y SANDLER.
                                    
                                    Contexto del Proyecto/Prospecto:
                                    - Cliente: {datos_proy['Cliente']} (Área: {area_planta})
                                    - Audiencia: {interlocutor}
                                    - Equipo/Servicio de interés: {datos_proy['Descripcion']}
                                    - Contexto de la Visita: {contexto_manual}
                                    
                                    REGLAS DE ESTILO METROLÓGICO:
                                    1. Di "micrómetros" (NO submicras), "incertidumbre expandida", "trazabilidad", "error máximo permitido", "acreditación EMA".
                                    2. Háblale de "tú" al cliente pero usando "Ing." (Ej. "¿Qué tal, Ing.?").
                                    
                                    INSTRUCCIÓN (VISITAS Y APERTURA):
                                    Genera un plan de 4 secciones:
                                    1. GUION PARA ABRIR PUERTAS (COLD/WARM APPROACH): Un mensaje o guion telefónico basado en la metodología Sandler (dolor) para conseguir la cita. Sin rodeos, mencionando un problema típico de {area_planta} relacionado con {datos_proy['Descripcion']}.
                                    2. PLAN DE VISITA A PLANTA (GEMBA WALK): Qué no hacer (no sacar el PowerPoint de inmediato) y qué pedir ver físicamente (la zona de rechazos, la CMM actual, el cuello de botella).
                                    3. PREGUNTAS SPIN DE DIAGNÓSTICO: 3 preguntas de Implicación (la "I" de SPIN) a realizar durante el recorrido en planta para dimensionar el costo de no resolver el problema.
                                    4. COREOGRAFÍA DE ACOMPAÑAMIENTO (ROLES): Si el vendedor va con el PM, el PM es el francotirador técnico; el vendedor dirige la reunión. Si va con Martín Becerra, Martín aborda negociaciones de TCO. Si va con Óscar Morales, Óscar alinea estratégicamente con el Gerente de Planta. Define cómo presentar al acompañante.
                                    """
                                else:
                                    prompt_maestro = f"""
                                    Eres un experto en Revenue Operations, ventas B2B industriales, y especialista senior de MESS Servicios Metrológicos. Dominas las metodologías SPIN, MEDDPICC y SANDLER, así como Account-Based Marketing (ABM).
                                    
                                    Contexto del Proyecto Activo:
                                    - Cliente: {datos_proy['Cliente']}
                                    - ID Proyecto: {datos_proy['ID_Proyecto']}
                                    - Equipo/Servicio: {datos_proy['Descripcion']}
                                    - Monto: ${datos_proy['Monto_USD']:,.2f} USD / ${datos_proy['Monto_MXN']:,.2f} MXN
                                    - Audiencia: {interlocutor} (Área: {area_planta})
                                    - Notas: {contexto_manual}
                                    
                                    REGLAS DE ESTILO METROLÓGICO:
                                    1. Di "micrómetros" (NO submicras), "incertidumbre expandida", "trazabilidad", "error máximo permitido", "acreditación EMA".
                                    2. Háblale de "tú" pero usando "Ing.".
                                    3. LÓGICA DE METODOLOGÍA:
                                       - Si el monto es BAJO (<$1,000 USD): Aplica SANDLER (forzar el SÍ o NO inmediato, sin desgastes).
                                       - Si el monto es ALTO (>$2,000 USD): Aplica SPIN/MEDDPICC (ROI, implicaciones, riesgo operativo).
                                    
                                    INSTRUCCIÓN (CIERRE Y ACELERACIÓN):
                                    Genera:
                                    1. ESTRATEGIA Y CONSEJOS TÁCTICOS (Justifica Sandler o SPIN según el monto).
                                    2. ESTRATEGIA DE MARKETING B2B (1 o 2 acciones ABM precisas para que Marketing apoye el cierre, ej. enviar caso de éxito o invitar a webinar).
                                    3. MENSAJE DE WHATSAPP (Directo, persuasivo, "Ing.").
                                    4. CORREO EJECUTIVO (Call to Action claro).
                                    5. GUION DE LLAMADA Y MANEJO DE OBJECIONES.
                                    6. == TEXTO LISTO PARA PEGAR EN SCOTT ==.
                                    """
                                
                                response = model.generate_content(prompt_maestro)
                                
                                # GUARDAR EN SESIÓN PARA NO PERDERLO AL PRESIONAR DESCARGAR
                                st.session_state.tactica_generada = response.text
                                st.session_state.tactica_cliente = datos_proy['Cliente']
                                st.session_state.tactica_id = datos_proy['ID_Proyecto']
                                
                            except Exception as e:
                                st.error(f"Error de conexión con la API de Gemini: {e}")

                # === MOSTRAR ESTRATEGIA Y BOTONES DE EXPORTACIÓN ===
                if st.session_state.tactica_generada:
                    st.success("Táctica generada y guardada en memoria temporal.")
                    st.write(st.session_state.tactica_generada)
                    
                    st.divider()
                    st.markdown("#### 📤 Exportar y Guardar Bitácora")
                    st.caption("Comparte el mensaje directo al cliente o guarda el documento para reportes RevOps.")
                    
                    col_export1, col_export2 = st.columns(2)
                    
                    # BOTÓN WHATSAPP
                    with col_export1:
                        texto_url = urllib.parse.quote(st.session_state.tactica_generada)
                        url_whatsapp = f"https://wa.me/?text={texto_url}"
                        st.link_button("📲 Abrir en WhatsApp (Copiar Texto)", url_whatsapp, use_container_width=True)
                        
                    # BOTÓN WORD
                    with col_export2:
                        if docx_disponible:
                            # Generar Word al vuelo
                            doc = Document()
                            doc.add_heading(f"Bitácora Táctica: {st.session_state.tactica_cliente}", 0)
                            doc.add_heading(f"Proyecto ID: {st.session_state.tactica_id}", 1)
                            doc.add_paragraph(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                            doc.add_paragraph(st.session_state.tactica_generada)
                            
                            buffer = io.BytesIO()
                            doc.save(buffer)
                            buffer.seek(0)
                            
                            st.download_button(
                                label="📄 Descargar Bitácora (.docx)",
                                data=buffer,
                                file_name=f"Bitacora_{st.session_state.tactica_id}_{datetime.now().strftime('%Y%m%d')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                        else:
                            st.warning("⚠️ Para descargar en Word, instala: `pip install python-docx`")
                            st.download_button(
                                label="📄 Descargar Bitácora (.txt)",
                                data=st.session_state.tactica_generada.encode('utf-8'),
                                file_name=f"Bitacora_{st.session_state.tactica_id}.txt",
                                mime="text/plain",
                                use_container_width=True
                            )
                else:
                    if not gemini_activo:
                        st.warning("Agrega tu clave gemini_api_key en los Secrets para activar el Laboratorio Táctico.")

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
else:
    st.info("Sube el reporte comercial formato CSV (Plantilla Radar) para iniciar tu cuarto de estrategia.")
