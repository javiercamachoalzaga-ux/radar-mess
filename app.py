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

archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott (Histórico Completo)", type=["csv"])

if archivo_cargado is not None:
    try:
        # 1. Leemos el archivo asegurando que Pandas maneje los duplicados de Scott
        df = pd.read_csv(archivo_cargado, encoding='latin-1')
        
        # Eliminamos espacios al inicio y final de los nombres de columnas
        df.columns = df.columns.str.strip()
        
        # Eliminamos filas que no tengan un cliente válido
        df = df.dropna(subset=['CLIENTE'])
        
        # 2. Traductor Ampliado
        traductor = {
            "COTIZACION": "Cotización", 
            "CLIENTE": "Cliente", 
            "FECHA": "Fecha_Creacion", 
            "FECHA DE REGISTRO": "Fecha_Registro",
            "FECHA DE CIERRE": "Fecha_Cierre",
            "ESTATUS": "Estatus",
            "PROYECTO": "ID_Proyecto",
            "DESCRIPCION": "Descripcion",
            "CATEGORIA": "Categoria",
            "CONTACTO": "Nombre_Contacto"
        }
        df = df.rename(columns=lambda x: traductor.get(x, x))
        
        df['Cliente'] = df['Cliente'].astype(str).str.strip()
        if 'Estatus' not in df.columns: df['Estatus'] = 'EN PROCESO'
        df['Estatus'] = df['Estatus'].astype(str).str.strip().str.upper()
        
        # 3. Procesamiento blindado de Dinero (Revisa las posibles columnas de "VALOR")
        def procesar_mxn(val_str):
            val_str = str(val_str).upper()
            if 'USD' in val_str or val_str == 'NAN': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        def procesar_usd(val_str):
            val_str = str(val_str).upper()
            if 'USD' not in val_str or val_str == 'NAN': return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        # Sumamos si Scott arrojó dos columnas de valor diferentes
        val_col_1 = df.get('VALOR', pd.Series(['0']*len(df))).astype(str)
        val_col_2 = df.get('VALOR.1', pd.Series(['0']*len(df))).astype(str) # Pandas renombra duplicados con .1
        
        df['Monto_MXN'] = val_col_1.apply(procesar_mxn) + val_col_2.apply(procesar_mxn)
        df['Monto_USD'] = val_col_1.apply(procesar_usd) + val_col_2.apply(procesar_usd)
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

        # 6. Preparación de Pestañas Activas y Visión Ampliada
        df_activas = df[df['Estatus'].str.contains('PROCESO', na=False)].copy()
        
        if 'Fecha_Creacion' in df_activas.columns:
            df_activas['SLA'] = (pd.Timestamp.now().normalize() - pd.to_datetime(df_activas['Fecha_Creacion'], errors='coerce')).dt.days
            df_activas['SLA'] = df_activas['SLA'].apply(lambda d: "⚪ S/F" if pd.isna(d) else ("🔴 +3 días" if d >= 3 else ("🟡 2 días" if d == 2 else "🟢 Reciente")))
        else:
            df_activas['SLA'] = "⚪ N/A"

        def estrategia(fila):
            if fila['Prioridad'] == "⭐ TOP 10": return "🚨 RIESGO: Visita técnica." if "🔴" in fila['SLA'] else ("📞 ALERTA: Llamada consultiva." if "🟡" in fila['SLA'] else "✉️ SEGUIMIENTO: Correo.")
            else: return "💼 ALTO VALOR: Visita/Llamada." if fila['Peso_Interno_Orden'] > 15000 else ("⏱️ 80/20: Descartar rápido." if "🔴" in fila['SLA'] else "📱 CONTACTO: WhatsApp.")

        df_activas['Estrategia_Cierre'] = df_activas.apply(estrategia, axis=1)
        df_activas = df_activas.sort_values(by='Peso_Interno_Orden', ascending=False)
        
        # AQUI AGREGAMOS TODAS LAS COLUMNAS QUE PEDISTE VER
        cols_ideales = ['SLA', 'Cotización', 'ID_Proyecto', 'Cliente', 'Nombre_Contacto', 'Categoria', 'Descripcion', 'Fecha_Creacion', 'Fecha_Cierre', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        cols_vista = [c for c in cols_ideales if c in df_activas.columns]

        # Filtros Tácticos
        df_vip = df_activas[df_activas['Prioridad'] == "⭐ TOP 10"].copy()
        df_normal = df_activas[df_activas['Prioridad'] == "Normal"].copy()
        ranking_normal = df_normal.groupby('Cliente')['Peso_Interno_Orden'].sum().reset_index().sort_values(by='Peso_Interno_Orden', ascending=False)
        top_5_nombres = ranking_normal.head(5)['Cliente'].tolist()
        df_potencial = df_normal[df_normal['Cliente'].isin(top_5_nombres)].copy()
        df_general = df_normal[~df_normal['Cliente'].isin(top_5_nombres)].copy()

        # 7. Renderizado de Interfaz
        tab_dash, tab_proyectos, tab_vip, tab_potencial, tab_general = st.tabs(["📊 Dashboard", "📁 Proyectos", "🏆 VIP (Activas)", "🚀 Alertas", "📋 General"])

        with tab_dash:
            st.markdown("### 📈 Desempeño Histórico 2026")
            col_m, col_u = st.columns(2)
            with col_m:
                st.markdown("#### 🇲🇽 Mercado Nacional (MXN)")
                m1, m2 = st.columns(2)
                m1.metric("✅ Ganado MXN", f"${mxn_ganado:,.2f}")
                m2.metric("❌ Perdido MXN", f"${mxn_perdido:,.2f}")
                st.metric("⏳ En Proceso MXN", f"${mxn_proceso:,.2f}")
            with col_u:
                st.markdown("#### 🇺🇸 Mercado Extranjero (USD)")
                u1, u2 = st.columns(2)
                u1.metric("✅ Ganado USD", f"${usd_ganado:,.2f}")
                u2.metric("❌ Perdido USD", f"${usd_perdido:,.2f}")
                st.metric("⏳ En Proceso USD", f"${usd_proceso:,.2f}")

        with tab_proyectos:
            st.markdown("### 📁 Estatus Consolidado por Proyectos (Histórico)")
            if 'ID_Proyecto' in df.columns:
                # Quitamos nulos y agrupamos POR CLIENTE Y PROYECTO para no mezclar
                df_proyectos = df.dropna(subset=['ID_Proyecto']).copy()
                if not df_proyectos.empty:
                    def estatus_proyecto(est_list):
                        s = " ".join(est_list).upper()
                        return "✅ GANADO" if "GANAD" in s else ("⏳ EN PROCESO" if "PROCESO" in s else "❌ PERDIDO/CANCELADO")
                    
                    res_proy = df_proyectos.groupby(['ID_Proyecto', 'Cliente']).agg(
                        Cotizaciones=('Cotización', lambda x: ", ".join(x.dropna().unique())),
                        Categoria=('Categoria', lambda x: ", ".join(x.dropna().unique()) if 'Categoria' in df_proyectos.columns else ""),
                        Descripcion=('Descripcion', lambda x: " | ".join(x.dropna().unique()) if 'Descripcion' in df_proyectos.columns else ""),
                        Total_MXN=('Monto_MXN', 'sum'),
                        Total_USD=('Monto_USD', 'sum'),
                        Creado=('Fecha_Creacion', 'min'),
                        Estatus_General=('Estatus', estatus_proyecto)
                    ).reset_index().sort_values(by='Total_MXN', ascending=False)
                    
                    st.dataframe(res_proy.style.format({'Total_MXN': '${:,.2f}', 'Total_USD': '${:,.2f}'}), use_container_width=True)
                else: st.info("Ninguna cotización tiene un número de proyecto asignado.")
            else: st.info("El archivo CSV no contiene la columna 'PROYECTO'.")

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
    st.write("Por favor sube tu archivo CSV histórico de Scott para empezar.")


         
      
   
                      
       
             
      
