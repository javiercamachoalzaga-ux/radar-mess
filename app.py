import streamlit as st
import pandas as pd
from datetime import datetime

# 1. Configuración de página
st.set_page_config(page_title="Radar MESS 80-20", layout="wide")

# 2. Seguridad
def check_password():
    st.sidebar.header("🔒 Acceso Restringido")
    pwd = st.sidebar.text_input("🔑 Contraseña", type="password")
    if "mi_contrasena" in st.secrets and pwd == st.secrets["mi_contrasena"]: return True
    return False

if not check_password():
    st.info("Ingresa tu contraseña en el menú lateral.")
    st.stop()

# 3. Interfaz y Carga
st.title("🎯 Radar de Cierres 80-20")
archivo_cargado = st.sidebar.file_uploader("Subir CSV de Scott", type=["csv"])

if archivo_cargado is not None:
    try:
        # Leemos y limpiamos
        df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
        df.columns = df.columns.str.strip()
        
        # Traductor
        traductor = {"COTIZACION": "Cotización", "CLIENTE": "Cliente", "VALOR": "Monto_Bruto", "FECHA": "Fecha_Registro"}
        df = df.rename(columns=lambda x: traductor.get(x, x))
        
        # --- 1. SEPARACIÓN DE MONEDAS ---
        def procesar_mxn(val_str):
            val_str = str(val_str).upper()
            if 'USD' in val_str: return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        def procesar_usd(val_str):
            val_str = str(val_str).upper()
            if 'USD' not in val_str: return 0.0
            try: return float(''.join(c for c in val_str if c.isdigit() or c == '.'))
            except: return 0.0

        df['Monto_MXN'] = df['Monto_Bruto'].apply(procesar_mxn)
        df['Monto_USD'] = df['Monto_Bruto'].apply(procesar_usd)

        # --- 2. ESCÁNER TOP 10 VIP ---
        top_10 = ["BOMBARDIER", "BROSE", "CNH", "DANA", "ITP", "SAFRAN", "SIEMENS", "STEERINGMEX", "TREMEC", "WATLOW"]
        
        def es_vip(cliente_str):
            cliente_str = str(cliente_str).upper()
            for marca in top_10:
                if marca in cliente_str: return "⭐ TOP 10"
            return "Normal"
            
        df['Prioridad'] = df['Cliente'].apply(es_vip)

        # --- 3. SEMÁFOROS SLA ---
        if 'Fecha_Registro' in df.columns:
            df['Fecha_Registro'] = pd.to_datetime(df['Fecha_Registro'], errors='coerce')
            dias_diff = (pd.Timestamp.now().normalize() - df['Fecha_Registro']).dt.days
            
            def semaforo(dias):
                if pd.isna(dias): return "⚪ S/F"
                if dias >= 3: return "🔴 +3 días"
                elif dias == 2: return "🟡 2 días"
                else: return "🟢 Reciente"
                
            df['SLA'] = dias_diff.apply(semaforo)
        else:
            df['SLA'] = "⚪ N/A"

        # Cálculo de valor total unificado para ordenamiento interno
        df['Valor_Orden'] = df['Monto_MXN'] + (df['Monto_USD'] * 19.50)

        # --- 4. MOTOR DE ESTRATEGIA (IA COMERCIAL) ---
        def generar_estrategia(fila):
            prioridad = fila['Prioridad']
            sla = fila['SLA']
            monto = fila['Valor_Orden']
            
            # Lógica de decisiones: Primero lo primero
            if prioridad == "⭐ TOP 10":
                if "🔴" in sla:
                    return "🚨 RIESGO: Visita presencial inmediata. Buscar acuerdo ganar-ganar. Validar si requieren soporte con equipos de medición de marcas de nuestra cartera principal (aclarar exclusiones si aplica)."
                elif "🟡" in sla:
                    return "📞 ALERTA: Llamada gerencial. Asegurar tiempos de entrega de calibración sin afectar su línea de producción. Mantener opciones simples."
                else:
                    return "✉️ SEGUIMIENTO: Correo consultivo. Confirmar recepción y ponerse a disposición técnica."
            else:
                if monto > 15000:
                    return "💼 ALTO VALOR: Agendar videollamada o visita técnica. Confirmar detalles del alcance acreditado (ej. verificar exclusión de escala HBW 5/250 si hay durómetros involucrados)."
                elif "🔴" in sla:
                    return "⏱️ 80/20: Llamada rápida de 5 min para intentar cierre. Si hay barreras, descartar para no mermar productividad."
                else:
                    return "📱 CONTACTO: Enviar WhatsApp de seguimiento para pulsar temperatura de compra."

        # Aplicamos la inteligencia a cada fila
        df['Estrategia_Cierre'] = df.apply(generar_estrategia, axis=1)

        # --- 5. ORDENAMIENTO 80-20 ---
        df['Es_VIP_Bool'] = df['Prioridad'] == "⭐ TOP 10"
        df = df.sort_values(by=['Es_VIP_Bool', 'Valor_Orden'], ascending=[False, False])

        # Preparamos la vista base
        columnas_finales = ['Prioridad', 'SLA', 'Cotización', 'Cliente', 'Monto_MXN', 'Monto_USD', 'Estrategia_Cierre']
        df_base = df[[c for c in columnas_finales if c in df.columns]]

        # --- 6. FILTRO DE CLIENTE DINÁMICO ---
        st.markdown("### 🔍 Análisis de Cuentas")
        lista_clientes = ["Todos"] + sorted(df_base['Cliente'].unique().tolist())
        cliente_seleccionado = st.selectbox("Selecciona un cliente para aislar sus cotizaciones:", lista_clientes)

        if cliente_seleccionado != "Todos":
            df_mostrar = df_base[df_base['Cliente'] == cliente_seleccionado]
        else:
            df_mostrar = df_base

        # --- VISUALIZACIÓN ---
        st.subheader("📊 Valor de la Selección")
        col1, col2 = st.columns(2)
        col1.metric("Total MXN", f"${df_mostrar['Monto_MXN'].sum():,.2f}")
        col2.metric("Total USD", f"${df_mostrar['Monto_USD'].sum():,.2f}")
        
        st.markdown("### 📋 Plan de Ataque")
        # El data_editor permite modificar la estrategia sugerida
        df_editado = st.data_editor(df_mostrar, hide_index=True, use_container_width=True)
        
        st.markdown("---")
        if st.download_button("📥 Descargar Plan Filtrado", data=df_editado.to_csv(index=False).encode('utf-8-sig'), file_name="Plan_Filtrado.csv"):
            st.success("¡Plan descargado! Éxito en tus cierres.")
            
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
else:
    st.write("Por favor sube tu archivo CSV de Scott para empezar.")
