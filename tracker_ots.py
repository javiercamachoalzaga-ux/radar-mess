import streamlit as st
import pandas as pd
import numpy as np
from pandas.tseries.offsets import BDay

st.set_page_config(page_title="MESS | Control de OVs y Facturación", layout="wide")

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"], table, th, td { 
        font-family: 'Montserrat', sans-serif !important; 
    }
    
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
        # LECTURA DEL ARCHIVO
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        df_clean['OV'] = buscar_col(["OV", "ORDEN DE VENTA", "ORDEN", "OT"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "NOMBRE CLIENTE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS", "ESTADO"])
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA", "FECHA OV", "FECHA DE REGISTRO", "CREACION"])
        df_clean['Factura'] = buscar_col(["FACTURA", "FOLIO FACTURA"])
        df_clean['Fecha_Factura'] = buscar_col(["FECHA FACTURA", "FECHA DE FACTURACION", "FECHA FACTURACION"])

        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
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

        df = df_clean.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].fillna('EN PROCESO').astype(str).str.strip().str.upper()

        # ==========================================
        # MOTOR DE AUDITORÍA Y SLA (7 Días Hábiles)
        # ==========================================
        df['Fecha_Creacion_DT'] = pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)
        df['Fecha_Factura_DT'] = pd.to_datetime(df['Fecha_Factura'], errors='coerce', dayfirst=True)
        
        df['Fecha_Limite'] = df['Fecha_Creacion_DT'] + BDay(7)
        
        # Inicializamos la columna numérica de retraso
        df['Dias_Retraso_Num'] = 0

        def auditar_sla(fila):
            estatus = str(fila['Estatus']).upper()
            if pd.isna(fila['Fecha_Limite']):
                return "[SIN FECHA] Revisar origen"
            
            hoy = pd.Timestamp.now().normalize()
            limite = fila['Fecha_Limite'].normalize()

            if "CANCELAD" in estatus:
                return "[CANCELADA]"
            
            if "GANAD" in estatus:
                if pd.isna(fila['Fecha_Factura_DT']):
                    return "[GANADA] Sin registro de fecha de factura"
                
                f_factura = fila['Fecha_Factura_DT'].normalize()
                if f_factura <= limite:
                    return "[GANADA EN TIEMPO] Factura dentro del SLA"
                else:
                    retraso_factura = np.busday_count(limite.date(), f_factura.date())
                    # Para las ganadas, registramos el retraso histórico pero no afectamos la mora viva
                    return f"[GANADA CON RETRASO] Se facturó {retraso_factura} días tarde"

            if hoy > limite:
                retraso_actual = np.busday_count(limite.date(), hoy.date())
                return f"[RETRASO] {retraso_actual} días hábiles"
            else:
                restantes = np.busday_count(hoy.date(), limite.date())
                return f"[EN TIEMPO] {restantes} días hábiles restantes"

        df['Alerta_SLA'] = df.apply(auditar_sla, axis=1)
        
        # Extraemos el valor numérico del retraso vivo para poder filtrar
        def extraer_dias_retraso(alerta):
            if "[RETRASO]" in alerta:
                try: return int(alerta.split("]")[1].split("días")[0].strip())
                except: return 0
            return 0
            
        df['Dias_Retraso_Num'] = df['Alerta_SLA'].apply(extraer_dias_retraso)

        # ==========================================
        # FILTRO ESTRATÉGICO DE RETRASOS (SIDEBAR)
        # ==========================================
        st.sidebar.divider()
        st.sidebar.header("Filtros Estratégicos")
        
        max_retraso = int(df['Dias_Retraso_Num'].max()) if not df.empty and df['Dias_Retraso_Num'].max() > 0 else 30
        
        filtro_dias_retraso = st.sidebar.slider(
            "Min. Días Hábiles de Retraso", 
            min_value=0, max_value=max_retraso, value=0, 
            help="Desliza para enfocarte solo en las OVs más rezagadas."
        )

        # SEPARACIÓN DE DATAFRAMES PARA EL DASHBOARD
        df_en_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        df_ganadas = df[df['Estatus'].str.contains('GANAD', na=False)].copy()

        df_retraso = df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('RETRASO', na=False)].sort_values(by='Dias_Retraso_Num', ascending=False)
        df_en_tiempo = df_en_proceso[df_en_proceso['Alerta_SLA'].str.contains('EN TIEMPO', na=False)].sort_values(by='Monto_MXN', ascending=False)
        
        st.sidebar.divider()
        st.sidebar.header("Resumen Operativo")
        st.sidebar.metric("Total OVs en Retraso", f"{len(df_retraso)} Órdenes")
        st.sidebar.metric("Valor en Retraso (MXN)", f"${df_retraso['Monto_MXN'].sum() + (df_retraso['Monto_USD'].sum() * 19.50):,.2f}")

        # PESTAÑAS CORPORATIVAS
        tab_dash, tab_retraso, tab_tiempo, tab_ganadas, tab_plan = st.tabs([
            "Resumen Global", "En Proceso (Retraso)", "En Proceso (En Tiempo)", "Auditoría Ganadas", "Plan de Acción"
        ])

        cols_vista = ['OV', 'Dias_Retraso_Num', 'Factura', 'Fecha_Factura', 'Cliente', 'Fecha_Creacion', 'Monto_MXN', 'Monto_USD', 'Estatus', 'Alerta_SLA']
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

        with tab_retraso:
            st.markdown("### Órdenes de Venta Fuera de Tiempo")
            if not df_retraso.empty:
                st.data_editor(df_retraso[cols_vista].drop(columns=['Dias_Retraso_Num']), hide_index=True, use_container_width=True)
            else:
                st.success("Excelente. No hay órdenes de venta retrasadas.")

        with tab_tiempo:
            st.markdown("### Órdenes de Venta en Proceso Normal")
            if not df_en_tiempo.empty:
                st.data_editor(df_en_tiempo[cols_vista].drop(columns=['Dias_Retraso_Num']), hide_index=True, use_container_width=True)
            else:
                st.info("No hay órdenes de venta en proceso normal actualmente.")

        with tab_ganadas:
            st.markdown("### Auditoría de Eficiencia Operativa (Ganadas)")
            if not df_ganadas.empty:
                filtro_ganadas = st.selectbox("Filtrar auditoría:", ["Ver Todas", "Solo Ganadas en Tiempo", "Solo Ganadas con Retraso"])
                df_g_mostrar = df_ganadas
                
                if filtro_ganadas == "Solo Ganadas en Tiempo":
                    df_g_mostrar = df_ganadas[df_ganadas['Alerta_SLA'].str.contains("EN TIEMPO")]
                elif filtro_ganadas == "Solo Ganadas con Retraso":
                    df_g_mostrar = df_ganadas[df_ganadas['Alerta_SLA'].str.contains("CON RETRASO")]
                    
                st.data_editor(df_g_mostrar[[c for c in cols_vista if c != 'Dias_Retraso_Num']].sort_values(by='Fecha_Creacion_DT', ascending=False), hide_index=True, use_container_width=True)
            else:
                st.info("No hay órdenes ganadas registradas para auditar.")

        with tab_plan:
            st.markdown("### Filtro Estratégico y Plan de Acción")
            st.write(f"Mostrando OVs 'En Proceso' con **{filtro_dias_retraso} o más días hábiles de retraso** (Ajusta el filtro en el menú lateral).")
            
            # Aplicamos el filtro estratégico
            df_plan = df_en_proceso[df_en_proceso['Dias_Retraso_Num'] >= filtro_dias_retraso].sort_values(by='Dias_Retraso_Num', ascending=False)
            
            if not df_plan.empty:
                df_plan.insert(0, 'Escalar_Hoy', False)
                
                # Ocultamos internamente el número pero mantenemos la alerta visible
                cols_edicion = ['Escalar_Hoy'] + [c for c in cols_vista if c != 'Dias_Retraso_Num']
                
                proyectos_accion = st.data_editor(
                    df_plan[cols_edicion], 
                    hide_index=True, use_container_width=True,
                    column_config={"Escalar_Hoy": st.column_config.CheckboxColumn("Escalar Hoy", default=False)}
                )
                
                plan_df = proyectos_accion[proyectos_accion['Escalar_Hoy'] == True]
                if not plan_df.empty:
                    st.markdown("#### Lista de Exigencia Seleccionada")
                    st.dataframe(plan_df.drop(columns=['Escalar_Hoy']).style.format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), use_container_width=True)
            else:
                st.success(f"No tienes OVs con más de {filtro_dias_retraso} días hábiles de retraso. Buen trabajo.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.info("Sube tu archivo de OVs para desplegar el panel.")
       
