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

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# CONFIGURACIÓN GEMINI API (3.6-FLASH)
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
if 'tactica_cliente' not in st.session_state: st.session_state.tactica_cliente = ""
if 'tactica_id' not in st.session_state: st.session_state.tactica_id = ""
if 'tactica_equipo' not in st.session_state: st.session_state.tactica_equipo = ""
if 'tactica_monto' not in st.session_state: st.session_state.tactica_monto = ""
if 'tactica_mensaje' not in st.session_state: st.session_state.tactica_mensaje = ""
if 'tactica_marketing' not in st.session_state: st.session_state.tactica_marketing = ""
if 'tactica_bitacora' not in st.session_state: st.session_state.tactica_bitacora = ""

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
            "2. Enablement Operativo", 
            "3. Laboratorio Táctico SCOTT (IA)"
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
            st.caption("Selecciona tu proyecto y personaliza la táctica exacta que necesitas hoy.")
            
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
                    <b>Equipo:</b> <span style='color:#003a70; font-weight:bold;'>{datos_proy['Descripcion']}</span> | 
                    <b>Monto:</b> ${datos_proy['Monto_USD']:,.2f} USD / ${datos_proy['Monto_MXN']:,.2f} MXN
                </div>
                """, unsafe_allow_html=True)
                
                # --- NUEVOS FILTROS DINÁMICOS ---
                tipo_operacion = st.radio("Objetivo Principal:", ["Aceleración y Cierre (Virtual)", "Apertura y Visitas (Presencial)"], horizontal=True)

                st.markdown("##### Configuración Específica")
                col_filtros1, col_filtros2 = st.columns(2)
                
                with col_filtros1:
                    if tipo_operacion == "Aceleración y Cierre (Virtual)":
                        sub_opcion = st.radio("¿Qué canal vas a usar?", ["Mensaje de WhatsApp", "Correo Electrónico Ejecutivo", "Guion de Llamada Telefónica"])
                    else:
                        sub_opcion = st.radio("¿Qué tipo de visita harás?", [
                            "Visita de Prospección (Primer Contacto)",
                            "Visita Técnica (Acompañado de Product Manager)",
                            "Visita de Negociación (Acompañado de Gerencia - Martín Becerra)",
                            "Visita Estratégica (Acompañado de Dirección - Óscar Morales)"
                        ])
                
                with col_filtros2:
                    interlocutor = st.selectbox("Perfil del Cliente (Quién lee/escucha):", ["Ingeniero / Calidad / Mantenimiento", "Comprador / Finanzas / Gerente de Planta"])
                    area_planta = st.selectbox("Área del Cliente:", ["Metrología / Control de Calidad", "Mantenimiento / Producción", "Compras / Sourcing"])
                
                contexto_manual = st.text_area("Notas breves (Ej. El cliente se queja del precio, o urge la calibración):", placeholder="Opcional...")
                
                st.divider()
                
                if gemini_activo:
                    if st.button("🧠 Generar Táctica Comercial", type="primary", use_container_width=True):
                        with st.spinner("Analizando, humanizando redacción y estructurando bitácora..."):
                            try:
                                # MOTOR OPTIMIZADO PARA PREVENIR CONGELAMIENTOS
                                model = genai.GenerativeModel(
                                    "gemini-3.6-flash",
                                    generation_config={
                                        "temperature": 0.3, 
                                        "max_output_tokens": 700, 
                                        "top_p": 0.8
                                    }
                                )
                                
                                prompt_maestro = f"""
                                Eres Javier Camacho, especialista B2B de MESS Servicios Metrológicos.
                                Estás escribiendo directamente, con tono MUY HUMANO, empático, profesional y natural. Cero formalismos excesivos. Eres un vendedor top hablando con su cliente de tú a tú, pero con respeto (usando "Ing.").
                                
                                DATOS DEL PROYECTO:
                                Cliente: {datos_proy['Cliente']} (Perfil: {interlocutor})
                                Equipo: {datos_proy['Descripcion']}
                                Monto: ${datos_proy['Monto_USD']} USD
                                Acción solicitada: {tipo_operacion} -> {sub_opcion}
                                Notas: {contexto_manual}
                                
                                INSTRUCCIONES ESTRICTAS:
                                Genera la respuesta dividida EXACTAMENTE en estas 3 etiquetas.

                                [MENSAJE]
                                Redacta el {sub_opcion}. Tiene que sonar natural. Lenguaje metrológico sutil pero directo al dolor.
                                [/MENSAJE]

                                [MARKETING]
                                Redacta 1 o 2 instrucciones claras para el departamento de Marketing (ABM) para respaldar el contacto.
                                [/MARKETING]

                                [BITACORA]
                                Redacta un párrafo altamente TÉCNICO-COMERCIAL para pegar en el CRM. Debe ser conciso, en tercera persona, resumiendo la acción y el "Next Step".
                                [/BITACORA]
                                """
                                
                                response = model.generate_content(prompt_maestro)
                                texto_raw = response.text
                                
                                # EXTRACTOR REGEX PARA SEPARAR CADA BLOQUE
                                match_mensaje = re.search(r'\[MENSAJE\](.*?)\[/MENSAJE\]', texto_raw, re.DOTALL)
                                match_mkt = re.search(r'\[MARKETING\](.*?)\[/MARKETING\]', texto_raw, re.DOTALL)
                                match_bitacora = re.search(r'\[BITACORA\](.*?)\[/BITACORA\]', texto_raw, re.DOTALL)
                                
                                st.session_state.tactica_mensaje = match_mensaje.group(1).strip() if match_mensaje else "Error aislando el mensaje."
                                st.session_state.tactica_marketing = match_mkt.group(1).strip() if match_mkt else "Error aislando marketing."
                                st.session_state.tactica_bitacora = match_bitacora.group(1).strip() if match_bitacora else texto_raw
                                
                                # GUARDAR TODO EL CONTEXTO PARA EL WORD
                                st.session_state.tactica_cliente = datos_proy['Cliente']
                                st.session_state.tactica_id = datos_proy['ID_Proyecto']
                                st.session_state.tactica_equipo = datos_proy['Descripcion']
                                st.session_state.tactica_monto = f"${datos_proy['Monto_USD']:,.2f} USD / ${datos_proy['Monto_MXN']:,.2f} MXN"
                                
                            except Exception as e:
                                st.error(f"Error con la IA: {e}")

                # === PANTALLA DE RESULTADOS SEGMENTADA ===
                if st.session_state.tactica_mensaje:
                    st.success("Táctica generada con éxito.")
                    
                    st.markdown("#### 💬 1. Tu Texto para el Cliente")
                    st.markdown(f"<div class='caja-ia'>{st.session_state.tactica_mensaje}</div>", unsafe_allow_html=True)
                    
                    st.markdown("#### 🎯 2. Táctica de Marketing Recomendada")
                    st.info(st.session_state.tactica_marketing)
                    
                    st.markdown("#### 📋 3. Reporte para Bitácora (Técnico/Concreto)")
                    st.warning(st.session_state.tactica_bitacora)
                    
                    st.divider()
                    st.markdown("### 📤 Central de Exportación")
                    
                    col_ex1, col_ex2, col_ex3 = st.columns(3)
                    
                    # 1. BOTÓN WHATSAPP / CORREO
                    with col_ex1:
                        if "WhatsApp" in sub_opcion:
                            texto_url = urllib.parse.quote(st.session_state.tactica_mensaje)
                            st.link_button("📲 Abrir en WhatsApp", f"https://wa.me/?text={texto_url}", use_container_width=True)
                        elif "Correo" in sub_opcion:
                            texto_url = urllib.parse.quote(st.session_state.tactica_mensaje)
                            st.link_button("✉️ Abrir en Outlook/Mail", f"mailto:?subject=Seguimiento Proyecto {st.session_state.tactica_id}&body={texto_url}", use_container_width=True)
                        else:
                            st.button("📞 Guion listo (Solo leer)", disabled=True, use_container_width=True)
                            
                    # 2. BOTÓN WORD (BITÁCORA COMPLETA 360°)
                    with col_ex2:
                        if docx_disponible:
                            # Esta función crea un documento estructurado sumando todos los datos
                            def crear_bitacora_completa():
                                doc = Document()
                                doc.add_heading("BITÁCORA TÁCTICA | REVENUE OPERATIONS", 0).alignment = 1
                                
                                # SECCIÓN 1: Contexto del Proyecto
                                doc.add_heading("1. Contexto del Proyecto", level=1)
                                p_ctx = doc.add_paragraph()
                                p_ctx.add_run("Cliente: ").bold = True
                                p_ctx.add_run(f"{st.session_state.tactica_cliente}\n")
                                p_ctx.add_run("Folio SCOTT: ").bold = True
                                p_ctx.add_run(f"{st.session_state.tactica_id}\n")
                                p_ctx.add_run("Equipo/Servicio: ").bold = True
                                p_ctx.add_run(f"{st.session_state.tactica_equipo}\n")
                                p_ctx.add_run("Valor en Riesgo: ").bold = True
                                p_ctx.add_run(f"{st.session_state.tactica_monto}\n")
                                p_ctx.add_run("Fecha de Generación: ").bold = True
                                p_ctx.add_run(f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
                                
                                # SECCIÓN 2: Resumen para CRM
                                doc.add_heading("2. Resumen Ejecutivo (Para registro en SCOTT)", level=1)
                                doc.add_paragraph(st.session_state.tactica_bitacora)
                                
                                # SECCIÓN 3: Acción Ejecutada
                                doc.add_heading(f"3. Acción Ejecutada ({sub_opcion})", level=1)
                                doc.add_paragraph(st.session_state.tactica_mensaje)
                                
                                # SECCIÓN 4: Marketing ABM
                                doc.add_heading("4. Instrucción Estratégica de Marketing (ABM)", level=1)
                                doc.add_paragraph(st.session_state.tactica_marketing)
                                
                                buffer = io.BytesIO()
                                doc.save(buffer)
                                buffer.seek(0)
                                return buffer

                            buffer_bitacora_completa = crear_bitacora_completa()
                            st.download_button("💾 Descargar Bitácora Completa (.docx)", data=buffer_bitacora_completa, file_name=f"Bitacora_Completa_{st.session_state.tactica_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

                    # 3. BOTÓN WORD (SÓLO MARKETING)
                    with col_ex3:
                        if docx_disponible:
                            def crear_word_mkt():
                                doc = Document()
                                doc.add_heading("SOLICITUD DE MARKETING (ABM)", 0).alignment = 1
                                doc.add_heading(f"Cliente: {st.session_state.tactica_cliente}", 1)
                                doc.add_paragraph(f"ID del Proyecto: {st.session_state.tactica_id} | Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                                doc.add_paragraph("_" * 50)
                                doc.add_paragraph(st.session_state.tactica_marketing)
                                buffer = io.BytesIO()
                                doc.save(buffer)
                                buffer.seek(0)
                                return buffer

                            buffer_mkt = crear_word_mkt()
                            st.download_button("📢 Exportar Solicitud de Marketing (.docx)", data=buffer_mkt, file_name=f"MKT_{st.session_state.tactica_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
