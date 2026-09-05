import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import re

st.set_page_config(page_title="MESS | Radar Comercial", layout="wide")

# ==========================================
# INICIALIZACIÓN DE MEMORIA (AGENDA Y CARRITO)
# ==========================================
if 'agenda_radar' not in st.session_state:
    st.session_state.agenda_radar = pd.DataFrame(columns=[
        'ID_Tarea', 'Fecha', 'Cliente', 'ID_Proyecto', 'Cotizacion', 
        'Unidad_Presupuesto', 'Monto_USD', 'Monto_MXN', 'Tipo_Accion', 'Descripcion', 'Completado'
    ])

if 'clear_key' not in st.session_state:
    st.session_state.clear_key = 0

if 'carrito' not in st.session_state:
    st.session_state.carrito = set()

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    .titulo-radar { font-size: 42px; font-weight: 900; color: #003a70; margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 16px; color: #555555; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px 20px; border-radius: 8px;
        border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
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

st.markdown('<div class="titulo-radar">Radar Comercial</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia de Cierres Diarios y Proyectos Vivos</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto", type=["csv"])

if archivo_cargado is not None:
    try:
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        
        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
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
            texto = str(texto)
            correcciones = {
                "L?SER": "LÁSER", "L?ser": "Láser", "Aut?noma": "Autónoma", "M?xico": "México",
                "M?XICO": "MÉXICO", "PE?A": "PEÑA", "MONTA?O": "MONTAÑO", "calibraci?n": "calibración",
                "CALIBRACI?N": "CALIBRACIÓN", "medici?n": "medición", "MEDICI?N": "MEDICIÓN",
                "t?cnico": "técnico", "T?CNICO": "TÉCNICO", "M?quina": "Máquina", "compresi?n": "compresión",
                "capacitaci?n": "capacitación", "cotizaci?n": "cotización", "n?mero": "número", "?": " "
            }
            for mal, bien in correcciones.items(): texto = texto.replace(mal, bien)
            texto = re.sub(r'\s+', ' ', texto).strip()
            
            palabras_menores = ['de', 'la', 'el', 'en', 'y', 'con', 'para', 'las', 'los']
            siglas = ['S.A.', 'C.V.', 'S.', 'R.L.', 'S.A.P.I.', 'LLC', 'INC', 'USD', 'MXN']
            
            resultado = []
            for p in texto.title().split():
                p_u = p.upper()
                if p.lower() in palabras_menores: resultado.append(p.lower())
                elif p_u in siglas or p_u.replace('.','').replace(',','') in siglas: resultado.append(p_u)
                else: resultado.append(p)
            return " ".join(resultado)

        for col in ['Cliente', 'Descripcion', 'Area', 'Estatus', 'Etapa']:
            df_clean[col] = df_clean[col].apply(limpiar_ortografia)

        mapeo_clientes = {
            "SAFRAN": "SAFRAN", "ITP": "ITP AERO", "DANA": "DANA", "BROSE": "BROSE", 
            "CNH": "CNH INDUSTRIAL", "BOMBARDIER": "BOMBARDIER", "TREMEC": "TREMEC", 
            "SIEMENS": "SIEMENS", "WATLOW": "WATLOW", "HAYAKAWA": "HAYAKAWA"
        }
        def unificar_cliente(nombre):
            nombre_u = str(nombre).upper()
            for clave, maestro in mapeo_clientes.items():
                if clave in nombre_u: return maestro
            return nombre.strip()

        df_clean['Cliente_Maestro'] = df_clean['Cliente'].apply(unificar_cliente)
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(
            lambda x: x.replace("", np.nan).ffill().bfill()
        )

        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn, monto_usd = pd.Series([0.0]*len(df_raw)), pd.Series([0.0]*len(df_raw))
        for col in df_raw.columns:
            if str(col).upper().strip().startswith("VALOR"):
                monto_mxn += df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                monto_usd += df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
        
        df_clean['Monto_MXN'] = monto_mxn
        df_clean['Monto_USD'] = monto_usd

        df = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first',
            'Cotizacion': lambda x: ' / '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Area': 'first',
            'Fecha_Creacion': 'first',
            'Fecha_Cierre': 'first',
            'Estatus': 'first',
            'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': 'sum',
            'Monto_USD': 'sum'
        }).reset_index()

        df.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        df = df[(df['Monto_MXN'] > 0) | (df['Monto_USD'] > 0) | (df['Cotizacion'] != "")]

        df = df[df['Estatus'].str.contains('PROCESO|PROPUESTA|COTIZACI|NEGOCIACI|PO|ORDEN', regex=True, case=False, na=False)].copy()
        
        def categorizar_unidad(area):
            a = str(area).upper()
            if any(k in a for k in ["ALTA GAMA", "EQUIPO", "CMM", "ZEISS", "SCANNER", "KREON", "BATY", "MITUTOYO"]): return "ALTA GAMA"
            elif any(k in a for k in ["LABORATORIO", "CALIBRACIÓN", "SERVICIO", "DIMENSIONAL"]): return "LABORATORIOS"
            return "PRODUCTOS" 
        df['Unidad_Presupuesto'] = df['Area'].apply(categorizar_unidad)

        # REDIRECCIÓN DEL MOTOR DE PIPELINE A LA COLUMNA "ETAPA"
        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if any(k in e for k in ['PO', 'ORDEN', 'ESPERANDO']): return "4. Esperando PO"
            elif 'NEGOCIACI' in e: return "3. Negociación"
            elif 'COTIZACI' in e: return "2. Cotización"
            elif 'PROPUESTA' in e: return "1. Propuesta"
            else: return "5. En Proceso (Otros)"
        df['Fase_Pipeline'] = df['Etapa'].apply(clasificar_fase)

        top_10_vip = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP AERO", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        df['Clasificacion_VIP'] = df['Cliente'].apply(lambda c: "VIP" if c.upper() in top_10_vip else "Normal")
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)
        
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Cierre_DT'] = pd.to_datetime(df['Fecha_Cierre'], errors='coerce', dayfirst=True)

        st.sidebar.divider()
        st.sidebar.header("Filtros Tácticos")
        
        busqueda_proyecto = st.sidebar.text_input("Buscar ID o Cliente:", placeholder="Ej. 111822 o SAFRAN")
        if busqueda_proyecto:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(busqueda_proyecto, case=False, na=False)) | 
                    (df['Cliente'].str.contains(busqueda_proyecto, case=False, na=False))]

        max_monto = float(df['Peso_Interno_Orden'].max()) if not df.empty else 1000000.0
        if pd.isna(max_monto) or max_monto == 0: max_monto = 100000.0
        
        rango_monto = st.sidebar.slider("Rango de Valor (Peso Interno)", 
                                    min_value=0.0, max_value=max_monto, 
                                    value=(0.0, max_monto), step=5000.0)
        df = df[(df['Peso_Interno_Orden'] >= rango_monto[0]) & (df['Peso_Interno_Orden'] <= rango_monto[1])]

        st.sidebar.divider()
        st.sidebar.header("Tubería Filtrada")
        st.sidebar.metric("Total USD en Filtro", f"${df['Monto_USD'].sum():,.2f}")
        st.sidebar.metric("Total MXN en Filtro", f"${df['Monto_MXN'].sum():,.2f}")

        contenedor_agenda_lateral = st.sidebar.container()

        mes_actual = pd.Timestamp.now().month
        anio_actual = pd.Timestamp.now().year
        
        tab_analisis, tab_implementacion, tab_ejecucion, tab_tiempo = st.tabs([
            "1. Inteligencia Financiera", 
            "2. Centro de Ejecución", 
            "3. Agenda de Trabajo",
            "4. Línea de Tiempo de Proyectos"
        ])

        with tab_analisis:
            st.markdown("### Dashboard de Cumplimiento y Presupuesto Mensual")
            st.caption("Seguimiento del pipeline comercial y cumplimiento de metas por unidad de negocio.")
            
            df_mes_tracker = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
            
            pipe_alta_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_USD'].sum()
            pipe_alta_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'ALTA GAMA']['Monto_MXN'].sum()
            pipe_labs_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_USD'].sum()
            pipe_labs_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'LABORATORIOS']['Monto_MXN'].sum()
            pipe_prod_usd = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_USD'].sum()
            pipe_prod_mxn = df_mes_tracker[df_mes_tracker['Unidad_Presupuesto'] == 'PRODUCTOS']['Monto_MXN'].sum()
            
            col_b1, col_b2, col_b3 = st.columns(3)
            col_b1.metric("Alta Gama (Meta: $28K USD)", f"${pipe_alta_usd:,.2f} USD", f"${pipe_alta_mxn:,.2f} MXN")
            col_b2.metric("Laboratorios (Meta: $15K USD)", f"${pipe_labs_usd:,.2f} USD", f"${pipe_labs_mxn:,.2f} MXN")
            col_b3.metric("Productos (Meta: $45K USD)", f"${pipe_prod_usd:,.2f} USD", f"${pipe_prod_mxn:,.2f} MXN")
            
            st.divider()
            st.markdown("### 📊 Embudo de Ventas (Fases del Pipeline Vivo)")
            df_pipeline = df.groupby('Fase_Pipeline').agg(
                Num_Proyectos=('ID_Proyecto', 'nunique'),
                Monto_USD=('Monto_USD', 'sum'),
                Monto_MXN=('Monto_MXN', 'sum')
            ).reset_index()
            
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            fases_core = ["1. Propuesta", "2. Cotización", "3. Negociación", "4. Esperando PO"]
            columnas = [col_p1, col_p2, col_p3, col_p4]
            
            for col, fase in zip(columnas, fases_core):
                data_fase = df_pipeline[df_pipeline['Fase_Pipeline'] == fase]
                if not data_fase.empty:
                    usd, mxn, proy = data_fase['Monto_USD'].iloc[0], data_fase['Monto_MXN'].iloc[0], data_fase['Num_Proyectos'].iloc[0]
                else:
                    usd, mxn, proy = 0.0, 0.0, 0
                with col:
                    st.metric(fase, f"{proy} Proyectos")
                    st.caption(f"**USD:** ${usd:,.2f} | **MXN:** ${mxn:,.2f}")
                    
            st.divider()
            
            st.markdown("### 🏢 Concentración de Capital en Cuentas VIP")
            df_vip = df[df['Clasificacion_VIP'] == "VIP"]
            if not df_vip.empty:
                st.bar_chart(df_vip.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum(), use_container_width=True, height=450)
            else:
                st.info("Sin proyectos activos en cuentas VIP.")
                
            st.markdown("### 📈 Distribución General por Área Comercial")
            if not df.empty:
                st.bar_chart(df.groupby('Area')[['Monto_MXN', 'Monto_USD']].sum(), use_container_width=True, height=450)

        def render_table_interactiva(df_subset, sufijo_clave):
            if df_subset.empty:
                st.info("Sin proyectos en esta unidad.")
                return
            df_mostrar = df_subset[['ID_Proyecto', 'Cliente', 'Fase_Pipeline', 'Cotizacion', 'Descripcion', 'Monto_USD', 'Monto_MXN']].copy()
            df_mostrar.insert(0, 'Seleccionar', df_mostrar['ID_Proyecto'].apply(lambda x: x in st.session_state.carrito))
            
            df_editado = st.data_editor(
                df_mostrar, hide_index=True, use_container_width=True,
                key=f"tabla_{sufijo_clave}_{st.session_state.clear_key}",
                column_config={
                    "Seleccionar": st.column_config.CheckboxColumn("Seleccionar"),
                    "Monto_USD": st.column_config.NumberColumn("Valor USD", format="$%.2f", disabled=True),
                    "Monto_MXN": st.column_config.NumberColumn("Valor MXN", format="$%.2f", disabled=True),
                    "Cliente": st.column_config.TextColumn(disabled=True),
                    "ID_Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                    "Fase_Pipeline": st.column_config.TextColumn("Fase", disabled=True),
                    "Cotizacion": st.column_config.TextColumn("Cotización(es)", disabled=True),
                    "Descripcion": st.column_config.TextColumn("Descripción", disabled=True)
                }
            )
            
            ids_en_vista = set(df_mostrar['ID_Proyecto'])
            ids_seleccionados = set(df_editado[df_editado['Seleccionar']]['ID_Proyecto'])
            st.session_state.carrito = (st.session_state.carrito - ids_en_vista) | ids_seleccionados

        def render_con_subpestanas(df_segmento, prefijo):
            t1, t2, t3 = st.tabs(["⚙️ Alta Gama", "🔬 Laboratorios", "📦 Productos"])
            with t1: render_table_interactiva(df_segmento[df_segmento['Unidad_Presupuesto'] == 'ALTA GAMA'], f"{prefijo}_ag")
            with t2: render_table_interactiva(df_segmento[df_segmento['Unidad_Presupuesto'] == 'LABORATORIOS'], f"{prefijo}_lb")
            with t3: render_table_interactiva(df_segmento[df_segmento['Unidad_Presupuesto'] == 'PRODUCTOS'], f"{prefijo}_pr")

        with tab_implementacion:
            st.markdown("### Centro de Control de Proyectos Vivos")
            st.caption("Visualiza tus proyectos rezagados y los cierres programados para el mes corriente.")
            
            inicio_mes_actual = pd.Timestamp(year=anio_actual, month=mes_actual, day=1)
            df_rezagados = df[df['Fecha_Creacion_DT'] < inicio_mes_actual].copy()
            
            st.markdown("#### 🔄 Proyectos de Arrastre / Rezagados")
            if not df_rezagados.empty:
                render_con_subpestanas(df_rezagados.sort_values('Peso_Interno_Orden', ascending=False), "rezagados")
            else:
                st.success("¡Excelente! No tienes proyectos rezagados de meses anteriores en proceso.")
            
            st.divider()

            st.markdown("#### 🎯 Estructura de Cierre del Mes Corriente")
            df_mes = df[(df['Fecha_Cierre_DT'].dt.month == mes_actual) & (df['Fecha_Cierre_DT'].dt.year == anio_actual)].copy()
            
            if not df_mes.empty:
                resumen_valor = df_mes.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index()
                resumen_valor = resumen_valor.sort_values(by='Peso_Interno_Orden', ascending=False)
                
                cliente_clave = resumen_valor.iloc[0]['Cliente'] if not resumen_valor.empty else ""
                df_cc = df_mes[df_mes['Cliente'] == cliente_clave].copy()
                df_resto = df_mes[df_mes['Cliente'] != cliente_clave].copy()
                
                st.markdown(f"##### 👑 CUENTA CLAVE DEL MES: {cliente_clave}")
                render_con_subpestanas(df_cc.sort_values('Peso_Interno_Orden', ascending=False), "cc")
                st.divider()

                def clasificar(fila):
                    if fila['Clasificacion_VIP'] == "VIP" or (fila['Monto_USD'] >= 10000 or fila['Monto_MXN'] >= 190000): return "TOP"
                    elif fila['Monto_USD'] <= 2500 and fila['Monto_MXN'] <= 45000: return "DESARROLLO"
                    else: return "80/20"
                
                if not df_resto.empty:
                    df_resto['Nivel'] = df_resto.apply(clasificar, axis=1)
                    
                    st.markdown("##### Prioridad TOP (Alto Valor o VIP)")
                    render_con_subpestanas(df_resto[df_resto['Nivel'] == "TOP"].sort_values('Peso_Interno_Orden', ascending=False), "top")
                    
                    st.markdown("##### Prioridad 80/20 (Maduración)")
                    render_con_subpestanas(df_resto[df_resto['Nivel'] == "80/20"].sort_values('Peso_Interno_Orden', ascending=False), "8020")
                    
                    st.markdown("##### Prioridad DESARROLLO")
                    render_con_subpestanas(df_resto[df_resto['Nivel'] == "DESARROLLO"].sort_values('Peso_Interno_Orden', ascending=False), "des")
            else:
                st.info("No hay proyectos con fecha de cierre programada para este mes.")

        with contenedor_agenda_lateral:
            st.header("🛒 Planeación de Ruta")
            if st.session_state.carrito:
                st.info(f"Proyectos en carrito listos para agendar: {len(st.session_state.carrito)}")
                
                df_carrito = df[df['ID_Proyecto'].isin(st.session_state.carrito)]
                
                accion_lote = st.selectbox("Acción a ejecutar:", ["Visita Presencial", "Llamada Consultiva", "Correo", "Cierre y Negociación"])
                fecha_lote = st.date_input("Fecha programada:", pd.Timestamp.now().date())
                
                if st.button("Agendar y Limpiar Carrito"):
                    for _, row in df_carrito.iterrows():
                        unidad = row.get('Unidad_Presupuesto', "Sin Área")
                        nueva_tarea = pd.DataFrame([{
                            'ID_Tarea': len(st.session_state.agenda_radar) + np.random.randint(1, 10000),
                            'Fecha': fecha_lote, 'Cliente': row['Cliente'], 'ID_Proyecto': row['ID_Proyecto'],
                            'Cotizacion': row['Cotizacion'], 'Unidad_Presupuesto': unidad,
                            'Monto_USD': row['Monto_USD'], 'Monto_MXN': row['Monto_MXN'],
                            'Tipo_Accion': accion_lote, 'Descripcion': row['Descripcion'], 'Completado': False
                        }])
                        st.session_state.agenda_radar = pd.concat([st.session_state.agenda_radar, nueva_tarea], ignore_index=True)
                    
                    st.session_state.carrito = set()
                    st.session_state.clear_key += 1
                    st.success("¡Actividades agendadas con éxito!")
                    st.rerun()
            else:
                st.info("Navega por las pestañas y selecciona los proyectos que deseas agendar.")

        with tab_ejecucion:
            st.markdown("### Tablero de Ejecución Diaria Multi-Cliente")
            fecha_vista = st.date_input("Seleccionar día a visualizar:", pd.Timestamp.now().date(), key="vista_fecha_agenda")
            df_dia = st.session_state.agenda_radar[st.session_state.agenda_radar['Fecha'] == fecha_vista].copy()
            
            if not df_dia.empty:
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Valor USD del Día", f"${df_dia['Monto_USD'].sum():,.2f} USD")
                col_m2.metric("Valor MXN del Día", f"${df_dia['Monto_MXN'].sum():,.2f} MXN")
                col_m3.metric("Total Actividades", f"{len(df_dia)}")
                col_m4.metric("Visitas Críticas", len(df_dia[df_dia['Tipo_Accion'] == "Visita Presencial"]))
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                df_dia_show = df_dia[['Completado', 'Cliente', 'ID_Proyecto', 'Cotizacion', 'Tipo_Accion', 'Monto_USD', 'Monto_MXN']].copy()
                proyectos_actualizados = st.data_editor(
                    df_dia_show, hide_index=True, use_container_width=True, key="editor_agenda_final",
                    column_config={
                        "Completado": st.column_config.CheckboxColumn("Realizado", default=False),
                        "Cliente": st.column_config.TextColumn("Cliente", disabled=True),
                        "ID_Proyecto": st.column_config.TextColumn("Proyecto", disabled=True),
                        "Cotizacion": st.column_config.TextColumn("Cotización", disabled=True),
                        "Tipo_Accion": st.column_config.TextColumn("Acción", disabled=True),
                        "Monto_USD": st.column_config.NumberColumn("USD", format="$%.2f", disabled=True),
                        "Monto_MXN": st.column_config.NumberColumn("MXN", format="$%.2f", disabled=True)
                    }
                )
                
                for i, idx in enumerate(df_dia.index):
                    st.session_state.agenda_radar.loc[idx, 'Completado'] = proyectos_actualizados.iloc[i]['Completado']
                
                st.divider()
                st.markdown("### Memorándum Profesional de Visita o Llamada")
                
                clientes_agenda = df_dia['Cliente'].unique().tolist()
                cliente_memo = st.selectbox("Generar memorándum para:", clientes_agenda)
                
                if cliente_memo:
                    df_memo = df_dia[df_dia['Cliente'] == cliente_memo]
                    suma_usd = df_memo['Monto_USD'].sum()
                    suma_mxn = df_memo['Monto_MXN'].sum()
                    
                    st.markdown(f"**Cliente / Planta:** {cliente_memo}")
                    st.markdown(f"**Valor en Discusión:** ${suma_usd:,.2f} USD | ${suma_mxn:,.2f} MXN")
                    st.markdown("**Proyectos y Cotizaciones Asociadas a la Cita:**")
                    
                    for _, row in df_memo.iterrows():
                        valor_str = f"${row['Monto_USD']:,.2f} USD" if row['Monto_USD'] > 0 else f"${row['Monto_MXN']:,.2f} MXN"
                        st.markdown(f"- **Proyecto ID {row['ID_Proyecto']} | Cotización: {row['Cotizacion']}**")
                        st.markdown(f"  *Alcance:* {row['Descripcion']} (Valor: {valor_str})")
                        
                    st.markdown("---")
                    st.markdown("*(Documento ejecutivo generado por MESS Servicios Metrológicos)*")
            else:
                st.info("Agenda libre para este día. Utiliza el Centro de Ejecución para programar cuentas.")

        with tab_tiempo:
            st.markdown("### ⏱️ Línea de Tiempo y Antigüedad de Proyectos")
            st.caption("Seguimiento del ciclo de vida. Los proyectos con más de 30 días desde su creación se resaltan en rojo para priorizar su atención.")
            
            if not df.empty:
                df_time = df[['ID_Proyecto', 'Cliente', 'Cotizacion', 'Fase_Pipeline', 'Fecha_Creacion_DT', 'Fecha_Cierre_DT', 'Monto_USD', 'Monto_MXN']].copy()
                
                hoy = pd.Timestamp.now()
                df_time['Días_Activo'] = (hoy - df_time['Fecha_Creacion_DT']).dt.days
                
                df_time['Fecha de Inicio'] = df_time['Fecha_Creacion_DT'].dt.strftime('%Y-%m-%d')
                df_time['Fecha de Cierre'] = df_time['Fecha_Cierre_DT'].dt.strftime('%Y-%m-%d')
                
                df_mostrar_tiempo = df_time[['ID_Proyecto', 'Cliente', 'Cotizacion', 'Fase_Pipeline', 'Fecha de Inicio', 'Fecha de Cierre', 'Días_Activo', 'Monto_USD', 'Monto_MXN']].copy()
                df_mostrar_tiempo.sort_values(by='Días_Activo', ascending=False, inplace=True)
                
                def highlight_retraso(row):
                    if pd.notnull(row['Días_Activo']) and row['Días_Activo'] > 30:
                        return ['background-color: #ffcccc; color: #900000'] * len(row)
                    return [''] * len(row)
                
                st.dataframe(
                    df_mostrar_tiempo.style.apply(highlight_retraso, axis=1).format({
                        'Monto_USD': '${:,.2f}',
                        'Monto_MXN': '${:,.2f}',
                        'Días_Activo': '{:.0f}'
                    }),
                    use_container_width=True,
                    height=650
                )
            else:
                st.info("Sin proyectos disponibles para generar la línea de tiempo.")

    except Exception as e:
        st.error(f"Error procesando el reporte: {e}")
else:
    st.info("Sube el reporte comercial formato CSV (Plantilla Radar) para iniciar.")
