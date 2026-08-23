import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Radar Comercial 80-20", layout="wide")

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

st.markdown('<div class="titulo-radar">⚡ Radar Comercial 80/20</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Inteligencia Táctica, Bateo y Proyectos 2026</div>', unsafe_allow_html=True)

archivo_cargado = st.sidebar.file_uploader("Subir CSV bruto de Scott (Sin modificar)", type=["csv"])

if archivo_cargado is not None:
    try:
        # 1. Lectura del archivo BRUTO de Scott
        df_raw = pd.read_csv(archivo_cargado, encoding='latin-1')
        
        # 2. MOTOR DE EXTRACCIÓN INTELIGENTE (Ignora duplicados y columnas basura)
        df_clean = pd.DataFrame()

        def buscar_col(palabras_clave):
            for clave in palabras_clave:
                for col in df_raw.columns:
                    # Limpiamos el nombre original quitando espacios y forzando mayúsculas
                    nombre_limpio = str(col).upper().strip()
                    # Si coincide con la clave original o con los duplicados que hace el sistema (.1, .2)
                    if nombre_limpio == clave or nombre_limpio == f"{clave}.1":
                        return df_raw[col].copy()
            return pd.Series([None] * len(df_raw))

        # Extracción quirúrgica
        df_clean['Cotización'] = buscar_col(["COTIZACION"])
        df_clean['Cliente'] = buscar_col(["CLIENTE"])
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Fecha_Cierre'] = buscar_col(["FECHA DE CIERRE"])
        df_clean['Estatus'] = buscar_col(["ESTATUS"])
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION"])
        df_clean['Categoria'] = buscar_col(["CATEGORIA"])
        df_clean['Nombre_Contacto'] = buscar_col(["CONTACTO"])

        # Fusión automática de todas las columnas de VALOR que Scott haya creado
        def extraer_numero(val_str):
            val_str = str(val_str).upper()
            if val_str == 'NAN' or val_str.strip() == '': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        monto_mxn_total = pd.Series([0.0] * len(df_raw))
        monto_usd_total = pd.Series([0.0] * len(df_raw))

        for col in df_raw.columns:
            nombre_limpio = str(col).upper().strip()
            # Si la columna es un valor financiero
            if nombre_limpio == "VALOR" or nombre_limpio.startswith("VALOR."):
                temp_mxn = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' not in str(x).upper() else 0.0)
                temp_usd = df_raw[col].apply(lambda x: extraer_numero(x) if 'USD' in str(x).upper() else 0.0)
                monto_mxn_total += temp_mxn
                monto_usd_total += temp_usd

        df_clean['Monto_MXN'] = monto_mxn_total
        df_clean['Monto_USD'] = monto_usd_total

        # Transferimos la tabla limpia para que el resto de la app trabaje sobre seguro
        df = df_clean

        # 3. Limpieza final de filas vacías
        df = df.dropna(subset=['Cliente'])
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        
        # Omitir filas que no sean clientes reales (ej. la fila vacía que detectamos antes)
        df = df[df['Cliente'].str.upper() != 'NAN']
        
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
            
        df['Peso_Interno_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # 4. Asignación VIP
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        df['Prioridad'] = df['Cliente'].apply(lambda c: "⭐ TOP 10" if any(m in c.upper() for m in top_10) else "Normal")

        # 5. Dashboard Histórico
        mxn_ganado = df[df['Estatus'].str.contains('GANAD', na=False)]['Monto_MXN'].sum()
        mxn_perdido = df[df['Estatus'].str.contains('PERDID|CANCELAD', na=False)]['Monto_MXN'].sum()
        mxn_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)]['Monto_MXN'].sum()
        
        usd_ganado = df[df['Estatus'].str.contains('GANAD', na=False)]['Monto_USD'].sum()
        usd_perdido = df[df['Estatus'].str.contains('PERDID|CANCELAD', na=False)]['Monto_USD'].sum()
        usd_proceso = df[df['Estatus'].str.contains('PROCESO', na=False)]['Monto_USD'].sum()
        
        tot_c_mxn = mxn_ganado + mxn_perdido
        tot_c_usd = usd_ganado + usd_perdido
        hr_mxn = (mxn_ganado / tot_c_mxn * 100) if tot_c_mxn > 0 else 0
        hr_usd = (usd_ganado / tot_c_usd * 100) if tot_c_usd > 0 else 0

        st.sidebar.markdown("---")
        st.sidebar.header("📈 Hit Rate Real")
        st.sidebar.metric("Bateo Histórico MXN", f"{hr_mxn:.1f}%")
        st.sidebar.metric("Bateo Histórico USD", f"{hr_usd:.1f}%")
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 Simulador Futuro")
        tasa_mxn = st.sidebar.slider("Simulador Bateo MXN (%)", 0, 100, int(hr_mxn) if hr_mxn > 0 else 30, 5)
        tasa_usd = st.sidebar.slider("Simulador Bateo USD (%)", 0, 100, int(hr_usd) if hr_usd > 0 else 30, 5)

        # 6. Preparación de Pestañas Activas y Táctica
        df_activas = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        
        if 'Fecha_Creacion' in df_activas.columns:
            df_activas['SLA'] = (pd.Timestamp.now().normalize() - pd.to_datetime(df_activas['Fecha_Creacion'], errors='coerce', dayfirst=True)).dt.days
            df_activas['SLA'] = df_activas['SLA'].apply(lambda d: "⚪ S/F" if pd.isna(d) else ("🔴 +3 días" if d >= 3 else ("🟡 2 días" if d == 2 else "🟢 Reciente")))
        else:
            df_activas['SLA'] = "⚪ N/A"

        def estrategia(fila):
            if fila['Prioridad'] == "⭐ TOP 10": return "🚨 RIESGO: Visita técnica." if "🔴" in fila['SLA'] else ("📞 ALERTA: Llamada consultiva." if "🟡" in fila['SLA'] else "✉️ SEGUIMIENTO: Correo.")
            else: return "💼 ALTO VALOR: Visita/Llamada." if fila['Peso_Interno_Orden'] > 15000 else ("⏱️ 80/20: Descartar rápido." if "🔴" in fila['SLA'] else "📱 CONTACTO: WhatsApp.")

        df_activas['Estrategia_Cierre'] = df_activas.apply(estrategia, axis=1)
        df_activas = df_activas.sort_values(by='Peso_Interno_Orden', ascending=False)
        
        cols_ideales = ['SLA', 'Cotización', 'ID_Proyecto', 'Cliente', 'Nombre_Contacto', 'Categoria', 'Descripcion', 'Fecha_Creacion', 'Fecha_Cierre', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        cols_vista = [c for c in cols_ideales if c in df_activas.columns]

        df_vip = df_activas[df_activas['Prioridad'] == "⭐ TOP 10"].copy()
        df_normal = df_activas[df_activas['Prioridad'] == "Normal"].copy()
        ranking_normal = df_normal.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index().sort_values(by='Peso_Interno_Orden', ascending=False)
        top_5_nombres = ranking_normal.head(5)['Cliente'].tolist()
        df_potencial = df_normal[df_normal['Cliente'].isin(top_5_nombres)].copy()
        df_general = df_normal[~df_normal['Cliente'].isin(top_5_nombres)].copy()

        # 7. Renderizado de Interfaz
        tab_dash, tab_proyectos, tab_vip, tab_potencial, tab_general = st.tabs(["📊 Dashboard", "📁 Proyectos", "🏆 VIP", "🚀 Alertas", "📋 General"])

        with tab_dash:
            st.markdown("### 📈 Desempeño Histórico 2026")
            col_m, col_u = st.columns(2)
            with col_m:
                st.markdown("#### 🇲🇽 Mercado Nacional (MXN)")
                m1, m2 = st.columns(2)
                m1.metric("✅ Ganado MXN", f"${mxn_ganado:,.2f}")
                m1.metric("❌ Perdido MXN", f"${mxn_perdido:,.2f}")
                st.metric("⏳ En Proceso MXN", f"${mxn_proceso:,.2f}")
            with col_u:
                st.markdown("#### 🇺🇸 Mercado Extranjero (USD)")
                u1, u2 = st.columns(2)
                u1.metric("✅ Ganado USD", f"${usd_ganado:,.2f}")
                u2.metric("❌ Perdido USD", f"${usd_perdido:,.2f}")
                st.metric("⏳ En Proceso USD", f"${usd_proceso:,.2f}")

        with tab_proyectos:
            st.markdown("### 📁 Estatus Consolidado y Fechas de Proyectos (Histórico)")
            if 'ID_Proyecto' in df.columns:
                df_proyectos = df.dropna(subset=['ID_Proyecto']).copy()
                if not df_proyectos.empty:
                    def estatus_proyecto(est_list):
                        s = " ".join([str(e) for e in est_list]).upper()
                        return "✅ GANADO" if "GANAD" in s else ("⏳ EN PROCESO" if "PROCESO" in s else "❌ PERDIDO/CANCELADO")

                    def fecha_minima(f_list):
                        fechas_validas = pd.to_datetime(f_list, errors='coerce', dayfirst=True).dropna()
                        if not fechas_validas.empty:
                            return fechas_validas.min().strftime('%d/%m/%Y')
                        return "Sin registro"

                    def fecha_maxima(f_list):
                        fechas_validas = pd.to_datetime(f_list, errors='coerce', dayfirst=True).dropna()
                        if not fechas_validas.empty:
                            return fechas_validas.max().strftime('%d/%m/%Y')
                        return "Sin registro"

                    agg_dict = {
                        'Cotización': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Cotización' in df_proyectos.columns else "",
                        'Categoria': lambda x: ", ".join(x.dropna().astype(str).unique()) if 'Categoria' in df_proyectos.columns else "",
                        'Descripcion': lambda x: " | ".join(x.dropna().astype(str).unique()) if 'Descripcion' in df_proyectos.columns else "",
                        'Monto_MXN': 'sum',
                        'Monto_USD': 'sum',
                        'Estatus': estatus_proyecto
                    }
                    
                    if 'Fecha_Creacion' in df_proyectos.columns:
                        agg_dict['Fecha_Creacion'] = fecha_minima
                    if 'Fecha_Cierre' in df_proyectos.columns:
                        agg_dict['Fecha_Cierre'] = fecha_maxima

                    res_proy = df_proyectos.groupby(['ID_Proyecto', 'Cliente']).agg(agg_dict).reset_index()
                    
                    renombres_proy = {
                        'Cotización': 'Cotizaciones',
                        'Monto_MXN': 'Total_MXN',
                        'Monto_USD': 'Total_USD',
                        'Estatus': 'Estatus_General',
                        'Fecha_Creacion': 'Fecha_Creacion',
                        'Fecha_Cierre': 'Fecha_Cierre'
                    }
                    res_proy = res_proy.rename(columns=renombres_proy)
                    
                    if 'Fecha_Cierre' in res_proy.columns:
                        def calcular_vigencia(fila):
                            if fila['Estatus_General'] != "⏳ EN PROCESO":
                                return "Cerrado"
                            f_cierre = pd.to_datetime(fila['Fecha_Cierre'], errors='coerce', dayfirst=True)
                            if pd.isna(f_cierre):
                                return "⚪ Sin Fecha"
                            dias = (f_cierre.normalize() - pd.Timestamp.now().normalize()).days
                            if dias < 0:
                                return f"🔴 VENCIDO ({abs(dias)}d)"
                            elif dias <= 5:
                                return f"🟡 Vence en {dias}d"
                            else:
                                return f"🟢 Vigente ({dias}d)"
                                
                        res_proy['Vigencia'] = res_proy.apply(calcular_vigencia, axis=1)
                        cols_orden = ['ID_Proyecto', 'Cliente', 'Estatus_General', 'Vigencia', 'Fecha_Creacion', 'Fecha_Cierre', 'Total_MXN', 'Total_USD', 'Categoria', 'Descripcion', 'Cotizaciones']
                        cols_finales_proy = [c for c in cols_orden if c in res_proy.columns]
                        res_proy = res_proy[cols_finales_proy]

                    res_proy = res_proy.sort_values(by='Total_MXN', ascending=False)
                    st.dataframe(res_proy.style.format({'Total_MXN': '${:,.2f}', 'Total_USD': '${:,.2f}'}), use_container_width=True)
                else:
                    st.info("Ninguna cotización tiene un número de proyecto asignado.")
            else:
                st.info("El archivo CSV no contiene la columna 'PROYECTO'.")

        with tab_vip:
            if not df_vip.empty:
                sel = st.selectbox("Filtrar VIP:", ["Todos"] + sorted(df_vip['Cliente'].unique().tolist()), key="f_vip")
                df_m = df_vip if sel == "Todos" else df_vip[df_vip['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_vip_{sel}")

        with tab_potencial:
            if not df_potencial.empty:
                sel = st.selectbox("Filtrar Emergentes:", ["Todos"] + sorted(df_potencial['Cliente'].unique().tolist()), key="f_pot")
                df_m = df_potencial if sel == "Todos" else df_potencial[df_potencial['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_pot_{sel}")

        with tab_general:
            if not df_general.empty:
                sel = st.selectbox("Filtrar Base:", ["Todos"] + sorted(df_general['Cliente'].unique().tolist()), key="f_gral")
                df_m = df_general if sel == "Todos" else df_general[df_general['Cliente'] == sel]
                st.data_editor(df_m[cols_vista], hide_index=True, use_container_width=True, key=f"t_gral_{sel}")

    except Exception as e:
        st.error(f"Error al procesar el archivo. Detalles: {e}")
else:
    st.write("Por favor sube tu archivo bruto (Directo de Scott) para empezar.")
          

             
      
