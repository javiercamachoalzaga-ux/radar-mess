import streamlit as st
import pandas as pd
import numpy as np  #

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Montserrat', sans-serif !important; 
    }
    
    /* Header Corporativo */
    .titulo-radar {
        font-size: 42px; 
        font-weight: 900;
        color: #003a70;
        margin-bottom: -5px;
        letter-spacing: -1px;
        text-transform: uppercase;
    }
    .subtitulo { 
        font-size: 16px; 
        color: #555555; 
        margin-bottom: 30px; 
        font-weight: 600; 
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* Tarjetas de Métricas */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px 20px;
        border-radius: 8px;
        border-left: 5px solid #003a70;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #7f8c8d !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #2c3e50 !important;
    }

    /* Pestañas (Tabs) Estilizadas */
    button[role="tab"] {
        font-weight: 700 !important;
        font-size: 14px !important;
        padding-bottom: 10px !important;
        text-transform: uppercase;
        color: #7f8c8d !important;
    }
    button[role="tab"][aria-selected="true"] {
        color: #003a70 !important;
        border-bottom-color: #003a70 !important;
    }
    
    /* === CORRECCIÓN DE CONTRASTE EN SIDEBAR === */
    [data-testid="stSidebar"] {
        background-color: #f4f6f7 !important;
        border-right: 1px solid #e0e0e0;
    }
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
        color: #003a70 !important;
        font-weight: 600;
    }
    .stTextInput input {
        color: #000000 !important;
        background-color: #ffffff !important;
        border: 1px solid #b2bec3 !important;
    }
    </style>
    """, unsafe_allow_html=True)

def check_password():
    st.sidebar.header("Acceso Restringido")
    pwd = st.sidebar.text_input("Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral para acceder al sistema.")
    st.stop()

# Logo en el menú lateral
try:
    st.sidebar.image("logo mess 1.jpg", use_container_width=True)
except:
    pass

st.markdown('<div class="titulo-radar">Radar Comercial</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia de Cierres Diarios y Proyectos Vivos</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto de Scott", type=["csv"])

if archivo_cargado is not None:
    try:
        # 1. LECTURA Y EXTRACCIÓN INTELIGENTE
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        df_clean['Cotización'] = buscar_col(["COTIZACION"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"]) # NUEVO: Extracción de Área
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])

        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn_total = pd.Series([0.0] * len(df_raw))
        monto_usd_total = pd.Series([0.0] * len(df_raw))

        for col in df_raw.columns:
            nombre_limpio = str(col).upper().strip()
            if nombre_limpio == "VALOR" or nombre_limpio.startswith("VALOR."):
                temp_mxn = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                temp_usd = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
                monto_mxn_total += temp_mxn
                monto_usd_total += temp_usd

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total

        df = df_clean

        # 2. FILTRO ESTRICTO: SOLO LO VIVO
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
        if 'Area' not in df.columns: df['Area'] = 'SIN ÁREA'
        df['Area'] = df['Area'].fillna('SIN ÁREA').astype(str).str.strip().str.upper()
        
        df = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)

        # ==========================================
        # 3. FILTROS TÁCTICOS (MENÚ LATERAL)
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("Filtros Tácticos")
        
        busqueda_proyecto = st.sidebar.text_input("🔍 Buscar ID de Proyecto o Cliente:", placeholder="Ej. 111822 o SAFRAN")
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]

        max_monto = float(df['Peso_Interno_Orden'].max()) if not df.empty else 1000000.0
        if pd.isna(max_monto) or max_monto == 0: max_monto = 100000.0
        
        rango_monto = st.sidebar.slider("Rango de Monto (Eq. MXN)", 
                                      min_value=0.0, 
                                      max_value=max_monto, 
                                      value=(0.0, max_monto), 
                                      step=5000.0)

        tipo_filtro_fecha = st.sidebar.selectbox("Filtrar por Fecha:", ["Sin Filtro", "Fecha de Creación", "Fecha de Cierre"])
        
        df = df[(df['Peso_Interno_Orden'] >= rango_monto[0]) & (df['Peso_Interno_Orden'] <= rango_monto[1])]

        if tipo_filtro_fecha != "Sin Filtro":
            col_fecha = 'Fecha_Creacion_DT' if tipo_filtro_fecha == "Fecha de Creación" else 'Fecha_Cierre_DT'
            min_date = df[col_fecha].min()
            max_date = df[col_fecha].max()
            
            if pd.notna(min_date) and pd.notna(max_date):
                fecha_rango = st.sidebar.date_input("Selecciona el rango:", [min_date.date(), max_date.date()])
                if len(fecha_rango) == 2:
                    f_ini, f_fin = fecha_rango
                    mask = (df[col_fecha].dt.date >= f_ini) & (df[col_fecha].dt.date <= f_fin)
                    incluir_vacios = st.sidebar.checkbox(f"Incluir registros sin {tipo_filtro_fecha}", value=True)
                    if incluir_vacios: df = df[mask | df[col_fecha].isna()]
                    else: df = df[mask]
            else:
                st.sidebar.warning(f"No hay registros válidos para el filtro de fecha.")

        st.sidebar.divider()
        
        # PANEL LATERAL RESUMIDO
        st.sidebar.header("Tubería (Filtrada)")
        st.sidebar.metric("Total MXN en Proceso", f"${df['Monto_MXN'].sum():,.2f}")
        st.sidebar.metric("Total USD en Proceso", f"${df['Monto_USD'].sum():,.2f}")

        # ==========================================
        # 4. ASIGNACIÓN VIP Y 80-20
        # ==========================================
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        df['Prioridad'] = df['Cliente'].apply(lambda c: "VIP" if any(m in c.upper() for m in top_10) else "Normal")

        df_vip = df[df['Prioridad'] == "VIP"].copy()
        df_normal = df[df['Prioridad'] == "Normal"].copy()
        
        ranking_normal = df_normal.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index().sort_values(by='Peso_Interno_Orden', ascending=False)
        nombres_80_20 = ranking_normal.head(10)['Cliente'].tolist()
        df_80_20 = df_normal[df_normal['Cliente'].isin(nombres_80_20)].copy()
        df_resto = df_normal[~df_normal['Cliente'].isin(nombres_80_20)].copy()

        # 5. CÁLCULOS DE SLA Y ESTRATEGIA DIARIA
        if 'Fecha_Creacion' in df.columns:
            df['SLA'] = (pd.Timestamp.now().normalize() - df['Fecha_Creacion_DT']).dt.days
            df['SLA'] = df['SLA'].apply(lambda d: "S/F" if pd.isna(d) else ("+3 Días" if d >= 3 else ("2 Días" if d == 2 else "Reciente")))
        else:
            df['SLA'] = "N/A"

        def estrategia(fila):
            if fila['Prioridad'] == "VIP": return "[RIESGO] Visita presencial" if "+3" in fila['SLA'] else ("[ALERTA] Llamada consultiva" if "2" in fila['SLA'] else "[SEGUIMIENTO] Correo")
            else: return "[ALTO VALOR] Priorizar cierre" if fila['Peso_Interno_Orden'] > 15000 else ("[80/20] Descartar rápido" if "+3" in fila['SLA'] else "[CONTACTO] WhatsApp")

        df['Estrategia_Cierre'] = df.apply(estrategia, axis=1)
        
        df_vip = df[df['Prioridad'] == "VIP"].sort_values(by='Peso_Interno_Orden', ascending=False)
        df_80_20 = df[df['Cliente'].isin(nombres_80_20)].sort_values(by='Peso_Interno_Orden', ascending=False)
        df_resto = df[~df['Cliente'].isin(nombres_80_20) & (df['Prioridad'] == "Normal")].sort_values(by='Peso_Interno_Orden', ascending=False)

        # Agregamos 'Area' a las columnas ideales para la vista
        cols_ideales = ['SLA', 'Cotización', 'ID_Proyecto', 'Area', 'Cliente', 'Descripcion', 'Fecha_Cierre', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        cols_vista = [c for c in cols_ideales if c in df.columns]

        # 6. RENDERIZADO DE PESTAÑAS
        tab_dash_vip, tab_dash_8020, tab_dash_areas, tab_proy, tab_plan, tab_op_vip, tab_op_8020, tab_gral = st.tabs([
            "Dash VIP", "Dash 80/20", "Dash Áreas", "Proyectos Vivos", "Plan de Acción", "Op. VIP", "Op. 80/20", "General"
        ])

        with tab_dash_vip:
            st.markdown("### Concentración de Capital: Cuentas VIP")
            if not df_vip.empty:
                col_m, col_u = st.columns(2)
                col_m.metric("Capital VIP (MXN)", f"${df_vip['Monto_MXN'].sum():,.2f}")
                col_u.metric("Capital VIP (USD)", f"${df_vip['Monto_USD'].sum():,.2f}")
                st.markdown("<br>", unsafe_allow_html=True)
                st.bar_chart(df_vip.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Cliente'), use_container_width=True)
            else:
                st.info("No hay cotizaciones vivas para cuentas VIP con los filtros actuales.")

        with tab_dash_8020:
            st.markdown("### Oportunidades de Alto Impacto (80/20)")
            if not df_80_20.empty:
                col_m, col_u = st.columns(2)
                col_m.metric("Capital 80/20 (MXN)", f"${df_80_20['Monto_MXN'].sum():,.2f}")
                col_u.metric("Capital 80/20 (USD)", f"${df_80_20['Monto_USD'].sum():,.2f}")
                st.markdown("<br>", unsafe_allow_html=True)
                st.bar_chart(df_80_20.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index().set_index('Cliente'), use_container_width=True)
            else:
                st.info("No hay datos suficientes para el segmento 80/20 con los filtros actuales.")

        # --- NUEVA PESTAÑA: DASHBOARD DE ÁREAS ---
        with tab_dash_areas:
            st.markdown("### Distribución por Unidades de Negocio (Equipos vs Laboratorios)")
            if not df.empty and 'Area' in df.columns:
                resumen_area = df.groupby('Area')[['Monto_MXN', 'Monto_USD']].sum().reset_index()
                resumen_area = resumen_area.sort_values(by='Monto_MXN', ascending=False)
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.dataframe(resumen_area.style.format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), use_container_width=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.bar_chart(resumen_area.set_index('Area'), use_container_width=True)
            else:
                st.info("No se encontró información de Áreas en el archivo actual.")

        proyectos_editados = pd.DataFrame()

        with tab_proy:
            st.markdown("### Selección de Prioridades (Proyectos Vivos)")
            st.caption("Marca la casilla 'Atender Hoy' para enviar los proyectos a tu Plan de Acción.")
            
            if 'ID_Proyecto' in df.columns:
                df_proyectos = df.dropna(subset=['ID_Proyecto']).copy()
                if not df_proyectos.empty:
                    def fecha_cierre_valida(f_list):
                        fechas_validas = pd.to_datetime(f_list, errors='coerce', dayfirst=True).dropna()
                        return fechas_validas.max().strftime('%d/%m/%Y') if not fechas_validas.empty else "Sin registro"

                    agg_dict = {
                        'Cotización': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Cotización' in df_proyectos.columns else "",
                        'Area': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Area' in df_proyectos.columns else "",
                        'Descripcion': lambda x: " | ".join(x.dropna().astype(str).unique()) if 'Descripcion' in df_proyectos.columns else "",
                        'Monto_MXN': 'sum',
                        'Monto_USD': 'sum'
                    }
                    if 'Fecha_Cierre' in df_proyectos.columns: agg_dict['Fecha_Cierre'] = fecha_cierre_valida

                    res_proy = df_proyectos.groupby(['ID_Proyecto', 'Cliente']).agg(agg_dict).reset_index()
                    res_proy = res_proy.rename(columns={'Cotización': 'Cotizaciones', 'Monto_MXN': 'Total_MXN', 'Monto_USD': 'Total_USD'})
                    
                    if 'Fecha_Cierre' in res_proy.columns:
                        def calcular_vigencia(fila):
                            f_cierre = pd.to_datetime(fila['Fecha_Cierre'], errors='coerce', dayfirst=True)
                            if pd.isna(f_cierre): return "Sin Fecha"
                            dias = (f_cierre.normalize() - pd.Timestamp.now().normalize()).days
                            if dias < 0: return f"VENCIDO ({abs(dias)}d)"
                            elif dias <= 5: return f"Vence en {dias}d"
                            else: return f"Vigente ({dias}d)"
                                
                        res_proy['Vigencia'] = res_proy.apply(calcular_vigencia, axis=1)
                        cols_orden = ['ID_Proyecto', 'Cliente', 'Area', 'Vigencia', 'Fecha_Cierre', 'Total_MXN', 'Total_USD', 'Descripcion', 'Cotizaciones']
                        res_proy = res_proy[[c for c in cols_orden if c in res_proy.columns]]

                    res_proy = res_proy.sort_values(by='Total_MXN', ascending=False)
                    res_proy.insert(0, 'Atender Hoy', False)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    proyectos_editados = st.data_editor(
                        res_proy, 
                        hide_index=True, 
                        use_container_width=True, 
                        key="editor_proyectos",
                        column_config={"Atender Hoy": st.column_config.CheckboxColumn("Atender Hoy", default=False)}
                    )
                else: st.info("No hay proyectos agrupados y vivos que cumplan con los filtros.")
            else: st.info("Falta la columna 'PROYECTO'.")

        with tab_plan:
            st.markdown("### Plan de Acción del Día")
            if not proyectos_editados.empty:
                plan_df = proyectos_editados[proyectos_editados['Atender Hoy'] == True].copy()
                
                if not plan_df.empty:
                    st.success("Objetivos fijados. Este es tu objetivo de cierre para la jornada.")
                    col1, col2 = st.columns(2)
                    col1.metric("Objetivo MXN a Cerrar", f"${plan_df['Total_MXN'].sum():,.2f}")
                    col2.metric("Objetivo USD a Cerrar", f"${plan_df['Total_USD'].sum():,.2f}")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.dataframe(plan_df.drop(columns=['Atender Hoy']).style.format({'Total_MXN': '${:,.2f}', 'Total_USD': '${:,.2f}'}), use_container_width=True)
                else:
                    st.info("Aún no has seleccionado ningún proyecto. Ve a la pestaña 'Proyectos Vivos' y marca tus prioridades.")
            else:
                st.info("Ajusta tus filtros o carga tu archivo para generar tu plan de acción.")

        with tab_op_vip:
            st.markdown("### Detalle Operativo VIP")
            if not df_vip.empty:
                sel = st.selectbox("Filtrar VIP:", ["Todos"] + sorted(df_vip['Cliente'].unique().tolist()), key="f_vip")
                df_m = df_vip if sel == "Todos" else df_vip[df_vip['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel}")
            else:
                st.info("Sin registros.")

        with tab_op_8020:
            st.markdown("### Detalle Operativo 80/20")
            if not df_80_20.empty:
                sel = st.selectbox("Filtrar Emergentes (Top 10):", ["Todos"] + sorted(df_80_20['Cliente'].unique().tolist()), key="f_pot")
                df_m = df_80_20 if sel == "Todos" else df_80_20[df_80_20['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel}")
            else:
                st.info("Sin registros.")

        with tab_gral:
            st.markdown("### Seguimiento General (Menor Prioridad)")
            if not df_resto.empty:
                sel = st.selectbox("Filtrar Base:", ["Todos"] + sorted(df_resto['Cliente'].unique().tolist()), key="f_gral")
                df_m = df_resto if sel == "Todos" else df_resto[df_resto['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel}")
            else:
                st.info("Sin registros.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.info("Sube tu archivo bruto de Scott para desplegar el panel táctico.")
# ==========================================
# MÓDULO: AGENDA COMERCIAL (RADAR DE VENTAS)
# ==========================================
st.divider()

# 1. Memoria de la agenda para el Radar
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=['ID_Tarea', 'Fecha', 'Cliente', 'Tipo_Accion', 'Completado'])

with st.expander("📅 AGENDA COMERCIAL Y PROSPECCIÓN", expanded=True):
    
    # 2. SECCIÓN DE ASIGNACIÓN
    st.markdown("#### ➕ Programar Seguimiento a Proyecto")
    
    with st.form("formulario_agenda_radar"):
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        
        with col_f1:
            # Intentamos leer tu DataFrame principal del Radar (usualmente se llama 'df')
            try:
                if 'ID_Proyecto' in df.columns:
                    lista_clientes = (df['Cliente'].astype(str) + " (ID: " + df['ID_Proyecto'].astype(str) + ")").unique()
                else:
                    lista_clientes = df['Cliente'].astype(str).unique()
            except:
                lista_clientes = ["Carga un archivo primero para ver tus clientes"]
                
            cliente_sel = st.selectbox("1. Selecciona el Cliente/Proyecto:", lista_clientes)
            
        with col_f2:
            accion_sel = st.selectbox("2. ¿Qué acción harás?", ["Llamada", "Visita Presencial", "Correo/Cotización"])
            
        with col_f3:
            fecha_sel = st.date_input("3. Fecha programada:", pd.Timestamp.now().date())
            
        btn_agendar = st.form_submit_button("Agendar a mi día")
        
        if btn_agendar and cliente_sel != "Carga un archivo primero para ver tus clientes":
            nueva_tarea = pd.DataFrame([{
                'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1,1000),
                'Fecha': fecha_sel,
                'Cliente': cliente_sel,
                'Tipo_Accion': accion_sel,
                'Completado': False
            }])
            st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
            st.success(f"✅ Seguimiento agendado para el {fecha_sel.strftime('%d/%m/%Y')}.")
            
    st.divider()
    
    # 3. TABLERO DE EJECUCIÓN (TO-DO LIST)
    st.markdown("### 🎯 Tu Plan de Acción")
    fecha_vista = st.date_input("Revisar agenda del día:", pd.Timestamp.now().date(), key="vista_agenda_radar")
    
    df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
    
    if not df_dia.empty:
        df_llamadas = df_dia[df_dia['Tipo_Accion'] == "Llamada"]
        df_visitas = df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]
        df_correos = df_dia[df_dia['Tipo_Accion'] == "Correo/Cotización"]
        
        total_tareas = len(df_dia)
        tareas_completadas = 0
        
        col_a1, col_a2, col_a3 = st.columns(3)
        
        with col_a1:
            st.markdown("#### 📞 Llamadas")
            if not df_llamadas.empty:
                for idx, row in df_llamadas.iterrows():
                    marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                    if marcado: tareas_completadas += 1
                    st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
            else: st.caption("Libre.")
            
        with col_a2:
            st.markdown("#### 🚗 Visitas")
            if not df_visitas.empty:
                for idx, row in df_visitas.iterrows():
                    marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                    if marcado: tareas_completadas += 1
                    st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
            else: st.caption("Libre.")
            
        with col_a3:
            st.markdown("#### ✉️ Correos")
            if not df_correos.empty:
                for idx, row in df_correos.iterrows():
                    marcado = st.checkbox(row['Cliente'], value=row['Completado'], key=f"tk_{row['ID_Tarea']}")
                    if marcado: tareas_completadas += 1
                    st.session_state.agenda_radar.loc[st.session_state.agenda_radar['ID_Tarea'] == row['ID_Tarea'], 'Completado'] = marcado
            else: st.caption("Libre.")
            
        # BARRA DE PROGRESO
        st.divider()
        progreso = int((tareas_completadas / total_tareas) * 100)
        st.markdown(f"**Avance del Día: {progreso}%** ({tareas_completadas} de {total_tareas} cuentas contactadas)")
        st.progress(progreso)
        
        if progreso == 100:
            st.success("¡Meta diaria cumplida! Has cerrado todas tus actividades comerciales de hoy.")
            st.balloons()
            
        if st.button("🧹 Limpiar completadas de hoy"):
            st.session_state.agenda_radar = st.session_state.agenda_radar[~((st.session_state.agenda_radar['Fecha'] == fecha_vista) & (st.session_state.agenda_radar['Completado'] == True))]
            st.rerun()
            
    else:
        st.info(f"No tienes proyectos agendados para el {fecha_vista.strftime('%d/%m/%Y')}. Selecciona un cliente arriba para agregarlo a tu día.")
