import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="MESS | Control de OTs y Flujo", layout="wide")

# --- DISEÑO ESTÉTICO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    
    .titulo-radar {
        font-size: 42px; font-weight: 900; color: #003a70;
        margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase;
    }
    .subtitulo { 
        font-size: 16px; color: #555555; margin-bottom: 30px; 
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

st.markdown('<div class="titulo-radar">Control de OTs y Flujo</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Seguimiento de Operaciones, Facturación y Cobranza</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV de OTs/Facturación", type=["csv"])

if archivo_cargado is not None:
    try:
        # LECTURA DEL ARCHIVO
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        df_clean = pd.DataFrame()

        # EXTRACCIÓN INTELIGENTE
        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    nombre_limpio = str(col).upper().strip()
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        df_clean['OT'] = buscar_col(["OT", "ORDEN DE TRABAJO", "ORDEN"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS", "ESTADO"])
        df_clean['Fecha_Factura'] = buscar_col(["FECHA FACTURA", "FECHA DE FACTURACION", "FACTURADO"])
        df_clean['Fecha_Pago'] = buscar_col(["FECHA PAGO", "FECHA DE PAGO", "PROMESA DE PAGO", "VENCIMIENTO"])
        df_clean['Factura'] = buscar_col(["FACTURA", "FOLIO FACTURA"])

        # EXTRACCIÓN DE MONTO
        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn_total = pd.Series([0.0] * len(df_raw))
        monto_usd_total = pd.Series([0.0] * len(df_raw))

        for col in df_raw.columns:
            nombre_limpio = str(col).upper().strip()
            if nombre_limpio in ["VALOR", "MONTO", "IMPORTE"] or nombre_limpio.startswith("VALOR."):
                temp_mxn = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                temp_usd = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
                monto_mxn_total += temp_mxn
                monto_usd_total += temp_usd

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total

        df = df_clean.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN EJECUCIÓN'
        df['Estatus'] = df['Estatus'].fillna('EN EJECUCIÓN').astype(str).str.strip().str.upper()

        df['Fecha_Pago_DT'] = pd.to_datetime(df['Fecha_Pago'], errors='coerce', dayfirst=True)

        # CÁLCULO DE VIGENCIA DE PAGO (Días de mora)
        def calcular_mora(fila):
            if "PAGAD" in fila['Estatus']: return "✅ Pagado"
            if pd.isna(fila['Fecha_Pago_DT']): return "⚪ Sin Fecha de Pago"
            
            dias_restantes = (fila['Fecha_Pago_DT'].normalize() - pd.Timestamp.now().normalize()).days
            
            if dias_restantes < 0: return f"🔴 VENCIDO ({abs(dias_restantes)} días de mora)"
            elif dias_restantes <= 7: return f"🟡 Crítico (Vence en {dias_restantes}d)"
            else: return f"🟢 A tiempo ({dias_restantes}d restantes)"

        df['Alerta_Cobranza'] = df.apply(calcular_mora, axis=1)

        # SEPARACIÓN DE DATAFRAMES POR ESTATUS
        df_por_facturar = df[df['Estatus'].str.contains('POR FACTURAR|EJECUCI', na=False)].sort_values(by='Monto_MXN', ascending=False)
        df_facturado = df[df['Estatus'].str.contains('FACTURADO|PROCESO DE PAGO', na=False)].sort_values(by='Fecha_Pago_DT')
        
        # DASHBOARD LATERAL
        st.sidebar.divider()
        st.sidebar.header("💰 Resumen de Flujo")
        st.sidebar.metric("Dinero Atorado (Por Facturar)", f"${df_por_facturar['Monto_MXN'].sum() + (df_por_facturar['Monto_USD'].sum() * 19.50):,.2f} MXN Eq.")
        st.sidebar.metric("Dinero en la Calle (Por Cobrar)", f"${df_facturado['Monto_MXN'].sum() + (df_facturado['Monto_USD'].sum() * 19.50):,.2f} MXN Eq.")
        st.sidebar.divider()

        # PESTAÑAS
        tab_dash, tab_facturar, tab_cobranza, tab_plan_cobranza = st.tabs([
            "📊 Dash Flujo", "⏳ Por Facturar", "🚨 Cuentas por Cobrar", "🎯 Plan de Acción Diario"
        ])

        cols_vista = ['OT', 'Cliente', 'Factura', 'Fecha_Factura', 'Fecha_Pago', 'Monto_MXN', 'Monto_USD', 'Alerta_Cobranza']
        cols_vista = [c for c in cols_vista if c in df.columns]

        with tab_dash:
            st.markdown("### 📊 Pipeline de Efectivo")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### ⏳ Cuello de Botella (No Facturado)")
                st.metric("Total MXN No Facturado", f"${df_por_facturar['Monto_MXN'].sum():,.2f}")
                st.metric("Total USD No Facturado", f"${df_por_facturar['Monto_USD'].sum():,.2f}")
                if not df_por_facturar.empty:
                    st.bar_chart(df_por_facturar.groupby('Cliente')['Monto_MXN'].sum().reset_index().set_index('Cliente'))

            with col2:
                st.markdown("#### 🚨 Dinero en Tránsito (Facturado no Cobrado)")
                st.metric("Total MXN por Cobrar", f"${df_facturado['Monto_MXN'].sum():,.2f}")
                st.metric("Total USD por Cobrar", f"${df_facturado['Monto_USD'].sum():,.2f}")
                if not df_facturado.empty:
                    df_facturado['Peso_Mora'] = df_facturado['Monto_MXN'] + (df_facturado['Monto_USD']*19.50)
                    st.bar_chart(df_facturado.groupby('Cliente')['Peso_Mora'].sum().reset_index().set_index('Cliente'))

        with tab_facturar:
            st.markdown("### ⏳ Órdenes Listas para Facturar")
            st.write("Presiona al equipo de operaciones o administración para emitir estas facturas lo antes posible. Sin factura, no corre el tiempo de crédito.")
            if not df_por_facturar.empty:
                st.data_editor(df_por_facturar[['OT', 'Cliente', 'Estatus', 'Monto_MXN', 'Monto_USD']], hide_index=True, use_container_width=True)
            else:
                st.success("¡Excelente! No tienes trabajo atorado sin facturar.")

        with tab_cobranza:
            st.markdown("### 🚨 Cuentas por Cobrar (Aging)")
            st.write("Facturas emitidas y corriendo tiempo. Prioriza las marcadas en 🔴 VENCIDO.")
            if not df_facturado.empty:
                filtro_cliente = st.selectbox("Filtrar por Cliente:", ["Todos"] + sorted(df_facturado['Cliente'].unique().tolist()))
                df_mostrar = df_facturado if filtro_cliente == "Todos" else df_facturado[df_facturado['Cliente'] == filtro_cliente]
                st.data_editor(df_mostrar[cols_vista], hide_index=True, use_container_width=True)
            else:
                st.success("No hay cuentas pendientes de cobro.")

        proyectos_cobranza = pd.DataFrame()

        with tab_plan_cobranza:
            st.markdown("### 🎯 Plan de Llamadas de Cobranza / Seguimiento de OTs")
            st.write("Marca los clientes a los que les llamarás hoy para exigir el pago o destrabar la factura.")
            
            df_accion = pd.concat([df_por_facturar, df_facturado])
            if not df_accion.empty:
                df_accion.insert(0, '🎯 Llamar Hoy', False)
                
                proyectos_cobranza = st.data_editor(
                    df_accion[['🎯 Llamar Hoy'] + cols_vista], 
                    hide_index=True, use_container_width=True,
                    column_config={"🎯 Llamar Hoy": st.column_config.CheckboxColumn("🎯 Llamar Hoy", default=False)}
                )
                
                plan_df = proyectos_cobranza[proyectos_cobranza['🎯 Llamar Hoy'] == True]
                if not plan_df.empty:
                    st.success(f"Tienes {len(plan_df)} llamadas programadas para hoy. ¡A recuperar ese efectivo!")
                    st.dataframe(plan_df.drop(columns=['🎯 Llamar Hoy']).style.format({'Monto_MXN': '${:,.2f}', 'Monto_USD': '${:,.2f}'}), use_container_width=True)
            else:
                st.info("No hay datos activos para cobranza.")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.info("Sube tu archivo de OTs / Contabilidad para desplegar el panel.")
