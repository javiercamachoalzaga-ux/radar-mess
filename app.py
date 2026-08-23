import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Radar Comercial Activo", layout="wide")

st.markdown("""
    <style>
    html, body, [class*="css"]  { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important; }
    .titulo-radar {
        font-size: 42px; font-weight: 900;
        background: -webkit-linear-gradient(45deg, #1e3c72, #2a5298, #00C6FF);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: -10px;
    }
    .subtitulo { font-size: 16px; color: #6c757d; margin-bottom: 25px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

st.markdown('<div class="titulo-radar">⚡ Radar Comercial Activo</div>', unsafe_allow_html=True)
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
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])
        df_clean['Categoria'] = buscar_col(["CATEGORIA"])
        df_clean['Nombre_Contacto'] = buscar_col(["CONTACTO"])

        # Fusión automática de columnas de VALOR
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

        # 2. FILTRO ESTRICTO: SOLO LO VIVO (Día a Día)
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
        # ELIMINAMOS HISTÓRICO: Nos quedamos solo con lo que está En Proceso
        df = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
            
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # 3. ASIGNACIÓN VIP Y 80-20
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        df['Prioridad'] = df['Cliente'].apply(lambda c: "⭐ VIP" if any(m in c.upper() for m in top_10) else "Normal")

        df_vip = df[df['Prioridad'] == "⭐ VIP"].copy()
        df_normal = df[df['Prioridad'] == "Normal"].copy()
        
        # Identificamos a los "Heavy Hitters" del 80-20 (Top 10 clientes normales con más dinero)
        ranking_normal = df_normal.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index().sort_values(by='Peso_Interno_Orden', ascending=False)
        nombres_80_20 = ranking_normal.head(10)['Cliente'].tolist()
        df_80_20 = df_normal[df_normal['Cliente'].isin(nombres_80_20)].copy()
        df_resto = df_normal[~df_normal['Cliente'].isin(nombres_80_20)].copy()

        # 4. CÁLCULOS DE SLA Y ESTRATEGIA DIARIA
        if 'Fecha_Creacion' in df.columns:
            df['SLA'] = (pd.Timestamp.now().normalize() - pd.to_datetime(df['Fecha_Creacion'], errors='coerce', dayfirst=True)).dt.days
            df['SLA'] = df['SLA'].apply(lambda d: "⚪ S/F" if pd.isna(d) else ("🔴 +3 días" if d >= 3 else ("🟡 2 días" if d == 2 else "🟢 Reciente")))
        else:
            df['SLA'] = "⚪ N/A"

        def estrategia(fila):
            if fila['Prioridad'] == "⭐ VIP": return "🚨 RIESGO: Visita técnica presencial." if "🔴" in fila['SLA'] else ("📞 ALERTA: Llamada consultiva gerencial." if "🟡" in fila['SLA'] else "✉️ SEGUIMIENTO: Correo.")
            else: return "💼 ALTO VALOR: Priorizar cierre." if fila['Peso_Interno_Orden'] > 15000 else ("⏱️ 80/20: Descartar rápido." if "🔴" in fila['SLA'] else "📱 CONTACTO: WhatsApp.")

        df['Estrategia_Cierre'] = df.apply(estrategia, axis=1)
        
        # Actualizamos los sub-dataframes con las nuevas columnas calculadas
        df_vip = df[df['Prioridad'] == "⭐ VIP"].sort_values(by='Peso_Interno_Orden', ascending=False)
        df_80_20 = df[df['Cliente'].isin(nombres_80_20)].sort_values(by='Peso_Interno_Orden', ascending=False)
        df_resto = df[~df['Cliente'].isin(nombres_80_20) & (df['Prioridad'] == "Normal")].sort_values(by='Peso_Interno_Orden', ascending=False)

        cols_ideales = ['SLA', 'Cotización', 'ID_Proyecto', 'Cliente', 'Nombre_Contacto', 'Categoria', 'Descripcion', 'Fecha_Cierre', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        cols_vista = [c for c in cols_ideales if c in df.columns]

        # PANEL LATERAL RESUMIDO
        st.sidebar.markdown("---")
        st.sidebar.header("💰 Tubería Total (Viva)")
        st.sidebar.metric("Total MXN en Proceso", f"${df['Monto_MXN'].sum():,.2f}")
        st.sidebar.metric("Total USD en Proceso", f"${df['Monto_USD'].sum():,.2f}")

        # 5. RENDERIZADO DE PESTAÑAS TÁCTICAS
        tab_dash_vip, tab_dash_8020, tab_proy, tab_op_vip, tab_op_8020, tab_gral = st.tabs([
            "👑 Dash VIP", "🚀 Dash 80/20", "📁 Proyectos Vivos", "🏆 Operación VIP", "⚡ Operación 80/20", "📋 General"
        ])

        # --- DASHBOARD VIP ---
        with tab_dash_vip:
            st.markdown("### 👑 Concentración de Capital: Cuentas VIP")
            if not df_vip.empty:
                col_m, col_u = st.columns(2)
                col_m.metric("Capital VIP (MXN)", f"${df_vip['Monto_MXN'].sum():,.2f}")
                col_u.metric("Capital VIP (USD)", f"${df_vip['Monto_USD'].sum():,.2f}")
                
                st.markdown("#### Top Cuentas VIP por Volumen Vivo")
                resumen_vip = df_vip.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index()
                st.bar_chart(resumen_vip.set_index('Cliente'))
            else:
                st.info("No hay cotizaciones vivas para cuentas VIP en este momento.")

        # --- DASHBOARD 80/20 ---
        with tab_dash_8020:
            st.markdown("### 🚀 Oportunidades de Alto Impacto (80/20)")
            st.write("Estos son tus clientes fuera del Top 10 corporativo, pero que actualmente concentran el mayor volumen de dinero en la mesa.")
            if not df_80_20.empty:
                col_m, col_u = st.columns(2)
                col_m.metric("Capital 80/20 (MXN)", f"${df_80_20['Monto_MXN'].sum():,.2f}")
                col_u.metric("Capital 80/20 (USD)", f"${df_80_20['Monto_USD'].sum():,.2f}")
                
                st.markdown("#### Ranking de Cuentas Emergentes (Top 10)")
                resumen_8020 = df_80_20.groupby('Cliente')[['Monto_MXN', 'Monto_USD']].sum().reset_index()
                st.bar_chart(resumen_8020.set_index('Cliente'))
            else:
                st.info("No hay datos suficientes para el segmento 80/20.")

        # --- PROYECTOS VIVOS ---
        with tab_proy:
            st.markdown("### 📁 Proyectos Activos (Mes a Mes)")
            if 'ID_Proyecto' in df.columns:
                df_proyectos = df.dropna(subset=['ID_Proyecto']).copy()
                if not df_proyectos.empty:
                    def fecha_cierre_valida(f_list):
                        fechas_validas = pd.to_datetime(f_list, errors='coerce', dayfirst=True).dropna()
                        return fechas_validas.max().strftime('%d/%m/%Y') if not fechas_validas.empty else "Sin registro"

                    agg_dict = {
                        'Cotización': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Cotización' in df_proyectos.columns else "",
                        'Categoria': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Categoria' in df_proyectos.columns else "",
                        'Descripcion': lambda x: " | ".join(x.dropna().astype(str).unique()) if 'Descripcion' in df_proyectos.columns else "",
                        'Monto_MXN': 'sum',
                        'Monto_USD': 'sum'
                    }
                    if 'Fecha_Cierre' in df_proyectos.columns: agg_dict['Fecha_Cierre'] = fecha_cierre_valida

                    res_proy = df_proyectos.groupby(['ID_Proyecto', 'Cliente']).agg(agg_dict).reset_index()
                    
                    renombres = {'Cotización': 'Cotizaciones', 'Monto_MXN': 'Total_MXN', 'Monto_USD': 'Total_USD'}
                    res_proy = res_proy.rename(columns=renombres)
                    
                    if 'Fecha_Cierre' in res_proy.columns:
                        def calcular_vigencia(fila):
                            f_cierre = pd.to_datetime(fila['Fecha_Cierre'], errors='coerce', dayfirst=True)
                            if pd.isna(f_cierre): return "⚪ Sin Fecha"
                            dias = (f_cierre.normalize() - pd.Timestamp.now().normalize()).days
                            if dias < 0: return f"🔴 VENCIDO ({abs(dias)}d)"
                            elif dias <= 5: return f"🟡 Vence en {dias}d"
                            else: return f"🟢 Vigente ({dias}d)"
                                
                        res_proy['Vigencia'] = res_proy.apply(calcular_vigencia, axis=1)
                        cols_orden = ['ID_Proyecto', 'Cliente', 'Vigencia', 'Fecha_Cierre', 'Total_MXN', 'Total_USD', 'Categoria', 'Descripcion', 'Cotizaciones']
                        res_proy = res_proy[[c for c in cols_orden if c in res_proy.columns]]

                    res_proy = res_proy.sort_values(by='Total_MXN', ascending=False)
                    st.dataframe(res_proy.style.format({'Total_MXN': '${:,.2f}', 'Total_USD': '${:,.2f}'}), use_container_width=True)
                else: st.info("No hay proyectos agrupados y vivos actualmente.")
            else: st.info("Falta la columna 'PROYECTO'.")

        # --- OPERACIÓN VIP ---
        with tab_op_vip:
            if not df_vip.empty:
                sel = st.selectbox("Filtrar VIP:", ["Todos"] + sorted(df_vip['Cliente'].unique().tolist()), key="f_vip")
                df_m = df_vip if sel == "Todos" else df_vip[df_vip['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel}")

        # --- OPERACIÓN 80/20 ---
        with tab_op_8020:
            if not df_80_20.empty:
                sel = st.selectbox("Filtrar Emergentes (Top 10):", ["Todos"] + sorted(df_80_20['Cliente'].unique().tolist()), key="f_pot")
                df_m = df_80_20 if sel == "Todos" else df_80_20[df_80_20['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel}")

        # --- GENERAL ---
        with tab_gral:
            if not df_resto.empty:
                sel = st.selectbox("Filtrar Base (Menor Prioridad):", ["Todos"] + sorted(df_resto['Cliente'].unique().tolist()), key="f_gral")
                df_m = df_resto if sel == "Todos" else df_resto[df_resto['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel}")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.write("Por favor sube tu archivo bruto de Scott para empezar.")

       
       
     
