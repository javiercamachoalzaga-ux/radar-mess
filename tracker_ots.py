import streamlit as st
import pandas as pd
import numpy as np
import re
from pandas.tseries.offsets import BDay

st.set_page_config(page_title="MESS | Control de OVs y Facturación", layout="wide")

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"], table, th, td { font-family: 'Montserrat', sans-serif !important; }
    
    .titulo-radar {
        font-size: 38px; font-weight: 900; color: #003a70;
        margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase;
    }
    .subtitulo { 
        font-size: 15px; color: #555555; margin-bottom: 30px; 
        font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase;
    }

    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 15px 20px; border-radius: 8px;
        border-left: 5px solid #003a70; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important; font-weight: 700 !important;
        color: #7f8c8d !important; text-transform: uppercase;
    }
    div[data-testid="stMetricValue"] {
        font-size: 26px !important; font-weight: 800 !important; color: #2c3e50 !important;
    }

    button[role="tab"] {
        font-weight: 700 !important; font-size: 14px !important;
        padding-bottom: 10px !important; text-transform: uppercase; color: #7f8c8d !important;
    }
    button[role="tab"][aria-selected="true"] {
        color: #003a70 !important; border-bottom-color: #003a70 !important;
    }
    
    [data-testid="stSidebar"] { background-color: #f4f6f7 !important; border-right: 1px solid #e0e0e0; }
    [data-testid="stSidebar"] p, label, h1, h2, h3, span { color: #003a70 !important; font-weight: 600; }
    
    .stDataFrame { font-family: 'Montserrat', sans-serif !important; }
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

try:
    st.sidebar.image("logo mess 1.jpg", use_container_width=True)
except:
    pass

st.markdown('<div class="titulo-radar">Control de OVs y Facturación</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Auditoría Operativa y SLA de 7 Días Hábiles</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV de OVs", type=["csv"])

if archivo_cargado is not None:
    try:
        try:
            df_raw = pd.read_csv(archivo_cargado, encoding='utf-8-sig')
        except UnicodeDecodeError:
            archivo_cargado.seek(0)
            df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')

        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if clave in nombre_limpio:
                        return df_raw[col].copy()
            return pd.Series([''] * len(df_raw))

        df_clean['OV'] = buscar_col(["OV", "ORDEN DE VENTA", "ORDEN", "OT", "DOCUMENTO", "FOLIO", "NO. OV", "PEDIDO", "NUMERO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "NOMBRE CLIENTE", "RAZON SOCIAL", "EMPRESA"])
        df_clean['Estatus'] = buscar_col(["ESTATUS", "ESTADO", "STATUS"])
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA OV", "CREACION", "FECHA"])
        df_clean['Factura'] = buscar_col(["FACTURA", "FOLIO FACTURA", "NO. FACTURA", "DOCUMENTO FACTURA", "UUID", "FOLIO FISCAL"])

        def limpiar_ov(val):
            val_str = str(val).strip()
            if val_str.upper() in ['NAN', 'NONE', '']: return ""
            return re.sub(r'^[Aa](\d+)', r'\1', val_str)

        def limpiar_none(val):
            val_str = str(val).strip()
            return "" if val_str.upper() in ['NAN', 'NONE', ''] else val_str

        df_clean['OV'] = df_clean['OV'].apply(limpiar_ov)
        df_clean['Factura'] = df_clean['Factura'].apply(limpiar_none)

        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str in ['NAN', 'NONE', '']: return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn_total = pd.Series([0.0] * len(df_raw))
        monto_usd_total = pd.Series([0.0] * len(df_raw))

        for col in df_raw.columns:
            nombre_limpio = str(col).upper().strip()
            if nombre_limpio in ["VALOR", "MONTO", "IMPORTE", "SUBTOTAL", "TOTAL"] or nombre_limpio.startswith("VALOR."):
                temp_mxn = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                temp_usd = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
                monto_mxn_total += temp_mxn
                monto_usd_total += temp_usd

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total
        df_clean['Peso_Ordenamiento'] = df_clean['Monto_MXN'] + (df_clean['Monto_USD'] * 19.50)

        df = df_clean.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        df = df[df['Cliente'] != '']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].fillna('EN PROCESO').astype(str).str.strip().str.upper()

        # ==========================================
        # MOTOR DE AUDITORÍA Y SLA (7 Días Hábiles)
        # ==========================================
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Limite_Cálculo'] = df['Fecha_Creacion_DT'] + BDay(7)
        df['Fecha_Límite_Facturación'] = df['Fecha_Limite_Cálculo'].dt.strftime('%d/%m/%Y')
        df['Dias_Retraso_Num'] = 0

        def auditar_sla(fila):
            estatus = str(fila['Estatus']).upper()
            if pd.isna(fila['Fecha_Limite_Cálculo']): return "[SIN FECHA] Revisar origen"
            hoy = pd.Timestamp.now().normalize()
            limite = fila['Fecha_Limite_Cálculo'].normalize()

            if "CANCELAD" in estatus: return "[CANCELADA]"
            if "COMPLETAD" in estatus or "GANAD" in estatus: return "[COMPLETADA]"

            if hoy > limite:
                retraso_actual = np.busday_count(limite.date(), hoy.date())
                return f"[RETRASO] {retraso_actual} días hábiles"
            else:
                restantes = np.busday_count(hoy.date(), limite.date())
                return f"[EN TIEMPO] {restantes} días restantes"

        df['Alerta_SLA'] = df.apply(auditar_sla, axis=1)
        
        def extraer_dias_retraso(alerta):
            if "[RETRASO]" in alerta:
                try: return int(alerta.split("]")[1].split("días")[0].strip())
                except: return 0
            return 0
            
        df['Dias_Retraso_Num'] = df['Alerta_SLA'].apply(extraer_dias_retraso)

        # ==========================================
        # MOTOR DE COLORES (FORMATO CONDICIONAL)
        # ==========================================
        def aplicar_colores(row):
            estatus = str(row.get('Estatus', '')).upper()
            retraso = pd.to_numeric(row.get('Dias_Retraso_Num', 0), errors='coerce')
            
            # Verde claro para Completadas/Ganadas
            if "COMPLETAD" in estatus or "GANAD" in estatus:
                return ['background-color: #d4edda; color: #155724; font-weight: 500;'] * len(row)
            # Rojo claro para retrasos críticos (> 20 días)
            elif retraso > 20:
                return ['background-color: #f8d7da; color: #721c24; font-weight: 500;'] * len(row)
            return [''] * len(row)

        # ==========================================
        # FILTROS TÁCTICOS
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("🔍 Filtros Tácticos")
        
        busqueda_texto = st.sidebar.text_input("Buscar OV o Cliente:", placeholder="Ej. 12543 o SAFRAN")
        if busqueda_texto:
            df = df[(df['OV'].astype(str).str.contains(busqueda_texto, case=False, na=False)) |
                    (df['Cliente'].astype(str).str.contains(busqueda_texto, case=False, na=False))]

        max_monto = float(df['Peso_Ordenamiento'].max()) if not df.empty else 1000000.0
        if pd.isna(max_monto) or max_monto == 0: max_monto = 100000.0
        
        rango_monto = st.sidebar.slider("Valor Total (Eq. MXN)", 
                                      min_value=0.0, max_value=max_monto, 
                                      value=(0.0, max_monto), step=5000.0)
        df = df[(df['Peso_Ordenamiento'] >= rango_monto[0]) & (df['Peso_Ordenamiento'] <= rango_monto[1])]

        st.sidebar.divider()
        st.sidebar.header("Filtro de Riesgo (SLA)")
        
        max_retraso = int(df['Dias_Retraso_Num'].max()) if not df.empty and df['Dias_Retraso_Num'].max() > 0 else 30
        filtro_dias_retraso = st.sidebar.slider(
            "Min. Días Hábiles de Retraso", 
            min_value=0, max_value=max_retraso, value=0, 
            help="Desliza para enfocarte solo en las OVs más rezagadas."
        )

        df_en_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        df_ganadas = df[df['Estatus'].str.contains('COMPLETAD|GANAD', na=False)].copy()

        df_retraso = df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('RETRASO', na=False)].sort_values(by='Peso_Ordenamiento', ascending=False)
        df_en_tiempo = df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('EN TIEMPO', na=False)].sort_values(by='Peso_Ordenamiento', ascending=False)
        
        st.sidebar.divider()
        st.sidebar.header("Resumen Operativo Filtrado")
        st.sidebar.metric("OVs en Retraso", f"{len(df_retraso)} Órdenes")
        st.sidebar.metric("Retraso (MXN)", f"${df_retraso['Monto_MXN'].sum():,.2f}")
        st.sidebar.metric("Retraso (USD)", f"${df_retraso['Monto_USD'].sum():,.2f}")

        tab_dash, tab_kpi, tab_retraso, tab_tiempo, tab_ganadas, tab_plan = st.tabs([
            "Resumen Global", "Dashboard Ejecutivo", "En Proceso (Retraso)", "En Proceso (En Tiempo)", "Auditoría Completadas", "Plan de Acción (Reportes)"
        ])

        # Aseguramos que Dias_Retraso_Num y Estatus estén en cols_vista para que el motor de color funcione (las ocultaremos de la vista)
        cols_vista = ['OV', 'Factura', 'Cliente', 'Fecha_Creacion', 'Fecha_Límite_Facturación', 'Monto_MXN', 'Monto_USD', 'Alerta_SLA', 'Dias_Retraso_Num', 'Estatus']
        cols_vista = [c for c in cols_vista if c in df.columns]

        with tab_dash:
            st.markdown("### Estatus General de Órdenes de Venta (En Proceso)")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Foco Crítico (SLA Vencido)")
                st.metric("Total MXN en Riesgo", f"${df_retraso['Monto_MXN'].sum():,.2f}")
                st.metric("Total USD en Riesgo", f"${df_retraso['Monto_USD'].sum():,.2f}")
            with col2:
                st.markdown("#### Operación Saludable (Dentro de SLA)")
                st.metric("Total MXN en Tiempo", f"${df_en_tiempo['Monto_MXN'].sum():,.2f}")
                st.metric("Total USD en Tiempo", f"${df_en_tiempo['Monto_USD'].sum():,.2f}")

        with tab_kpi:
            st.markdown("### Indicadores Estratégicos de Desempeño")
            
            st.markdown("#### Foco de Riesgo: Clientes con mayor valor en retraso")
            if not df_retraso.empty:
                riesgo_clientes = df_retraso.groupby('Cliente').agg({'OV': 'count', 'Monto_MXN': 'sum', 'Monto_USD': 'sum', 'Peso_Ordenamiento': 'sum'}).reset_index()
                riesgo_clientes = riesgo_clientes.rename(columns={'OV': 'OVs_Atrasadas'})
                riesgo_clientes = riesgo_clientes.sort_values(by='Peso_Ordenamiento', ascending=False).head(10)
                
                col_r1, col_r2 = st.columns([3, 2])
                with col_r1:
                    st.dataframe(riesgo_clientes[['Cliente', 'OVs_Atrasadas', 'Monto_MXN', 'Monto_USD']].style.format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), hide_index=True, use_container_width=True)
                with col_r2:
                    st.bar_chart(riesgo_clientes.set_index('Cliente')[['Monto_MXN', 'Monto_USD']])
            else:
                st.success("No hay riesgo financiero por facturación retrasada en este momento.")
            
            st.divider()
            
            col_kpi1, col_kpi2 = st.columns(2)
            with col_kpi1:
                st.markdown("#### Eficiencia Actual (OVs En Proceso)")
                st.write("Proporción de OVs activas dentro del SLA vs. Retrasadas")
                conteo_tiempo = len(df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('EN TIEMPO')])
                conteo_retraso = len(df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('RETRASO')])
                
                if conteo_tiempo > 0 or conteo_retraso > 0:
                    df_sla_record = pd.DataFrame({
                        "Estatus Activo": ["Sanos (En Tiempo)", "Riesgo (Con Retraso)"],
                        "Total de OVs": [conteo_tiempo, conteo_retraso]
                    })
                    st.bar_chart(df_sla_record.set_index("Estatus Activo"))
                else:
                    st.info("Faltan datos para calcular eficiencia.")

            with col_kpi2:
                st.markdown("#### Top 10 Clientes por Facturación (Completadas)")
                if not df_ganadas.empty:
                    top_clientes = df_ganadas.groupby('Cliente').agg({'Monto_MXN': 'sum', 'Monto_USD': 'sum', 'Peso_Ordenamiento': 'sum'}).reset_index()
                    top_clientes = top_clientes.sort_values(by='Peso_Ordenamiento', ascending=False).head(10)
                    st.bar_chart(top_clientes.set_index('Cliente')[['Monto_MXN', 'Monto_USD']])
                else:
                    st.info("Sin OVs completadas para mostrar facturación.")

        with tab_retraso:
            st.markdown("### Órdenes de Venta Fuera de Tiempo")
            if not df_retraso.empty:
                st.data_editor(
                    df_retraso[cols_vista].style.apply(aplicar_colores, axis=1).format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), 
                    hide_index=True, use_container_width=True,
                    column_config={"Dias_Retraso_Num": None} # Oculta la columna numérica
                )
            else: st.success("No hay órdenes de venta retrasadas.")

        with tab_tiempo:
            st.markdown("### Órdenes de Venta en Proceso Normal")
            if not df_en_tiempo.empty:
                st.data_editor(
                    df_en_tiempo[cols_vista].style.apply(aplicar_colores, axis=1).format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), 
                    hide_index=True, use_container_width=True,
                    column_config={"Dias_Retraso_Num": None}
                )
            else: st.info("No hay órdenes en proceso normal.")

        with tab_ganadas:
            st.markdown("### Órdenes de Venta Completadas")
            if not df_ganadas.empty:
                df_ordenado = df_ganadas.sort_values(by='Fecha_Creacion_DT', ascending=False)
                st.data_editor(
                    df_ordenado[cols_vista].style.apply(aplicar_colores, axis=1).format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), 
                    hide_index=True, use_container_width=True,
                    column_config={"Dias_Retraso_Num": None}
                )
            else: st.info("No hay órdenes completadas registradas.")

        # ==========================================
        # TABLA COMPACTADA Y MOTOR DE REPORTES
        # ==========================================
        with tab_plan:
            st.markdown("### Reporte Masivo y Exigencia a Operaciones")
            st.write(f"Mostrando OVs en proceso con **{filtro_dias_retraso} o más días de retraso**.")
            
            df_plan = df_en_proceso[df_en_proceso['Dias_Retraso_Num'] >= filtro_dias_retraso].sort_values(by='Dias_Retraso_Num', ascending=False)
            
            if not df_plan.empty:
                st.markdown("#### 1. Exportar Reporte de Riesgo (CSV)")
                st.write("Descarga con un clic la lista completa filtrada para adjuntarla a tu correo directivo.")
                
                cols_exportacion = ['OV', 'Cliente', 'Dias_Retraso_Num', 'Monto_MXN', 'Monto_USD', 'Fecha_Creacion', 'Fecha_Límite_Facturación', 'Alerta_SLA']
                df_exportacion = df_plan[[c for c in cols_exportacion if c in df_plan.columns]]
                
                csv_bulk = df_exportacion.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label=f"📥 Descargar Reporte Completo ({len(df_plan)} OVs)",
                    data=csv_bulk,
                    file_name=f"Reporte_OVs_Retrasadas_{filtro_dias_retraso}dias.csv",
                    mime="text/csv",
                )
                
                st.divider()
                
                st.markdown("#### 2. Constructor de Correo Rápido (Opcional)")
                st.write("¿Quieres exigir solo por unas cuantas OVs? Selecciónalas en esta tabla para armar un texto automático.")
                
                df_plan.insert(0, 'Generar_Mensaje', False)
                cols_compactas = ['Generar_Mensaje', 'OV', 'Cliente', 'Dias_Retraso_Num', 'Monto_MXN', 'Monto_USD', 'Estatus']
                
                proyectos_accion = st.data_editor(
                    df_plan[[c for c in cols_compactas if c in df_plan.columns]].style.apply(aplicar_colores, axis=1).format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), 
                    hide_index=True, use_container_width=True,
                    column_config={
                        "Generar_Mensaje": st.column_config.CheckboxColumn("Seleccionar", default=False),
                        "Estatus": None # Ocultamos Estatus aquí para mantener la tabla limpia, pero lo usamos para el color
                    }
                )
                
                plan_df = proyectos_accion[proyectos_accion['Generar_Mensaje'] == True].copy()
                
                if not plan_df.empty:
                    st.markdown("**Texto generado listo para copiar:**")
                    ovs_list = ", ".join([str(ov) for ov in plan_df['OV'].dropna().tolist() if ov != ""])
                    if not ovs_list: ovs_list = "[Sin número de OV]"
                    
                    suma_mxn = plan_df['Monto_MXN'].sum()
                    suma_usd = plan_df['Monto_USD'].sum()
                    texto_dinero = []
                    if suma_mxn > 0: texto_dinero.append(f"${suma_mxn:,.2f} MXN")
                    if suma_usd > 0: texto_dinero.append(f"${suma_usd:,.2f} USD")
                    string_dinero = " y ".join(texto_dinero) if texto_dinero else "$0.00"
                    
                    mensaje = f"Hola equipo,\n\nSolicito su apoyo URGENTE para facturar las siguientes OVs que excedieron los 7 días hábiles:\n{ovs_list}\n\nValor total en riesgo: {string_dinero}.\n\nSaludos."
                    st.code(mensaje, language="text")
            else:
                st.success(f"No tienes OVs con más de {filtro_dias_retraso} días hábiles de retraso.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.info("Sube tu archivo de OVs para desplegar el panel.")
