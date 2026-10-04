import sqlite3
import pandas as pd
import streamlit as st

# ==========================================
# CONFIGURACIÓN DE PÁGINA Y ESTILO CORPORATIVO
# ==========================================
st.set_page_config(
    page_title="Radar Comercial | MESS Servicios Metrológicos",
    page_icon="🔬",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button { background-color: #0033a0; color: white; font-weight: 600; border-radius: 6px; border: none; }
    .stButton>button:hover { background-color: #002270; color: white; }
    .metric-card { background: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 2px 4px rgba(0,0,0,0.02); text-align: center; }
    .metric-value { font-size: 24px; font-weight: 800; color: #0033a0; }
    .metric-label { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin-top: 5px; }
    </style>
""",
    unsafe_allow_html=True,
)


# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS SQLITE (REVOPS)
# ==========================================
def init_db():
  conn = sqlite3.connect("mess_radar.db")
  cursor = conn.cursor()

  # Tabla Agenda
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            cliente TEXT,
            contacto TEXT,
            objetivo TEXT,
            estatus TEXT
        )
    """)

  # Tabla Reportes (Bitácora Post-Visita)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_rep TEXT,
            cliente TEXT,
            resumen TEXT,
            pain TEXT,
            monto REAL,
            probabilidad INTEGER,
            semana TEXT,
            siguiente_paso TEXT,
            proxima_fecha TEXT,
            estatus TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


def run_query(query, params=(), fetch=True):
  conn = sqlite3.connect("mess_radar.db")
  cursor = conn.cursor()
  cursor.execute(query, params)
  if fetch:
    data = cursor.fetchall()
    conn.close()
    return data
  conn.commit()
  conn.close()


# ==========================================
# ENCABEZADO Y NAVEGACIÓN PRINCIPAL
# ==========================================
st.markdown(
    """
    <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #0033a0; padding-bottom: 15px; margin-bottom: 25px;">
        <div>
            <h1 style="color: #0033a0; font-size: 28px; margin: 0; text-transform: uppercase;">Radar Comercial & RevOps</h1>
            <p style="color: #64748b; font-size: 13px; font-weight: 600; margin: 0;">MESS Servicios Metrológicos • Sistema de Inteligencia y Gestión Comercial</p>
        </div>
        <div style="background: #0033a0; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 800; font-size: 14px;">
            MESS
        </div>
    </div>
""",
    unsafe_allow_html=True,
)

# Definición de Estaciones (Menú Lateral)
estacion = st.sidebar.radio(
    "Estaciones de Trabajo",
    [
        "📊 1. Monitoreo de Pipeline",
        "🎯 2. Configuración de Cuentas",
        "⚙️ 3. Cotizador Automatizado",
        "🚀 4. Gestión Comercial (RevOps)",
    ],
)

# ==========================================
# ESTACIÓN 1: MONITOREO DE PIPELINE (INTACTO)
# ==========================================
if estacion == "📊 1. Monitoreo de Pipeline":
  st.markdown("### 📊 Monitoreo General de Pipeline Comercial")
  st.info(
      "Módulo principal para la supervisión y control del flujo de oportunidades"
      " comerciales activas."
  )
  # Espacio reservado para tu lógica original del módulo 1 si la requieres integrar exacto

# ==========================================
# ESTACIÓN 2: CONFIGURACIÓN DE CUENTAS (INTACTO)
# ==========================================
elif estacion == "🎯 2. Configuración de Cuentas":
  st.markdown("### 🎯 Configuración y Mantenimiento de Cuentas Clave")
  st.info(
      "Módulo operativo para la administración de clientes y cuentas"
      " estratégicas."
  )
  # Espacio reservado para tu lógica original del módulo 2 si la requieres integrar exacto

# ==========================================
# ESTACIÓN 3: COTIZADOR AUTOMATIZADO (INTACTO)
# ==========================================
elif estacion == "⚙️ 3. Cotizador Automatizado":
  st.markdown("### ⚙️ Generador de Cotizaciones y Propuestas")
  st.info(
      "Módulo especializado para el cálculo y emisión de ofertas técnicas y"
      " comerciales."
  )
  # Espacio reservado para tu lógica original del módulo 3 si la requieres integrar exacto

# ==========================================
# ESTACIÓN 4: GESTIÓN COMERCIAL (REVOPS) - NUEVO
# ==========================================
elif estacion == "🚀 4. Gestión Comercial (RevOps)":
  st.markdown(
      "### 🚀 Estación 4: Revenue Operations & Ejecución Comercial"
  )

  tab1, tab2, tab3, tab4 = st.tabs([
      "📅 Agenda de Visitas",
      "📝 Bitácora Post-Visita",
      "📈 Forecast Semanal",
      "📄 Generador de Reportes",
  ])

  # ------------------------------------------
  # SUBMÓDULO 1: AGENDA DE VISITAS
  # ------------------------------------------
  with tab1:
    st.subheader("📅 Programación y Control de Visitas Comerciales")

    with st.form("form_agenda", clear_on_submit=True):
      col1, col2, col3 = st.columns(3)
      with col1:
        f_fecha = st.date_input("Fecha de Visita")
        f_cliente = st.text_input("Empresa / Cliente")
      with col2:
        f_contacto = st.text_input("Contacto Clave")
        f_estatus = st.selectbox(
            "Estatus Inicial",
            ["Programada", "Confirmada", "Realizada", "Reprogramada"],
        )
      with col3:
        f_objetivo = st.text_area(
            "Objetivo de la Visita",
            placeholder="Ej. Presentación paquete 3x1...",
        )

      submitted_agenda = st.form_submit_button(
          "💾 Guardar Cita en la Agenda"
      )
      if submitted_agenda:
        if f_cliente:
          run_query(
              "INSERT INTO agenda (fecha, cliente, contacto, objetivo,"
              " estatus) VALUES (?, ?, ?, ?, ?)",
              (
                  str(f_fecha),
                  f_cliente,
                  f_contacto,
                  f_objetivo,
                  f_estatus,
              ),
              fetch=False,
          )
          st.success(f"Visita con {f_cliente} registrada exitosamente.")
          st.rerun()
        else:
          st.error("Por favor ingresa el nombre del cliente.")

    st.markdown("---")
    st.markdown("#### 📋 Visitas Registradas")
    visitas = run_query(
        "SELECT id, fecha, cliente, contacto, objetivo, estatus FROM agenda"
        " ORDER BY fecha DESC"
    )
    if visitas:
      df_agenda = pd.DataFrame(
          visitas,
          columns=[
              "ID",
              "Fecha",
              "Cliente",
              "Contacto",
              "Objetivo",
              "Estatus",
          ],
      )
      st.dataframe(df_agenda, use_container_width=True, hide_index=True)
    else:
      st.info("No hay visitas agendadas en este momento.")

  # ------------------------------------------
  # SUBMÓDULO 2: BITÁCORA POST-VISITA
  # ------------------------------------------
  with tab2:
    st.subheader("📝 Bitácora Comercial Post-Visita")

    with st.form("form_reporte", clear_on_submit=True):
      col1, col2, col3 = st.columns(3)
      with col1:
        r_fecha = st.date_input("Fecha del Reporte")
        r_cliente = st.text_input("Cliente Visitado")
        r_semana = st.selectbox("Semana Comercial", ["W1", "W2", "W3", "W4"])
      with col2:
        r_monto = st.number_input(
            "Monto Estimado ($ MXN)", min_value=0.0, step=1000.0, format="%.2f"
        )
        r_prob = st.slider("Probabilidad de Cierre (%)", 0, 100, 50, 5)
        r_estatus = st.selectbox(
            "Estatus de la Oportunidad",
            ["Prospecto", "Cotizado", "Negociación", "Cerrado Ganado"],
        )
      with col3:
        r_pain = st.text_area(
            "Dolores del Cliente (Pain)",
            placeholder="Ej. Paros de máquina, rechazos por GD&T...",
        )
        r_paso = st.text_input("Acuerdos / Siguiente Paso")
        r_prox_fecha = st.date_input("Próxima Fecha de Seguimiento")

      submitted_rep = st.form_submit_button("💾 Guardar Reporte en Bitácora")
      if submitted_rep:
        if r_cliente:
          run_query(
              "INSERT INTO reportes (fecha_rep, cliente, resumen, pain, monto,"
              " probabilidad, semana, siguiente_paso, proxima_fecha, estatus)"
              " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (
                  str(r_fecha),
                  r_cliente,
                  "Seguimiento comercial post-visita",
                  r_pain,
                  r_monto,
                  r_prob,
                  r_semana,
                  r_paso,
                  str(r_prox_fecha),
                  r_estatus,
              ),
              fetch=False,
          )
          st.success(
              f"Bitácora guardada correctamente para el cliente {r_cliente}."
          )
          st.rerun()
        else:
          st.error("Ingresa al menos el nombre del cliente.")

    st.markdown("---")
    st.markdown("#### 🗂️ Historial de Reportes Comerciales")
    reportes = run_query(
        "SELECT cliente, monto, probabilidad, semana, estatus, proxima_fecha"
        " FROM reportes ORDER BY fecha_rep DESC"
    )
    if reportes:
      df_rep = pd.DataFrame(
          reportes,
          columns=[
              "Cliente",
              "Monto (MXN)",
              "Probabilidad (%)",
              "Semana",
              "Estatus",
              "Próximo Seguimiento",
          ],
      )
      st.dataframe(df_rep, use_container_width=True, hide_index=True)
    else:
      st.info("No hay reportes comerciales registrados.")

  # ------------------------------------------
  # SUBMÓDULO 3: FORECAST SEMANAL
  # ------------------------------------------
  with tab3:
    st.subheader("📈 Panel de Forecast y Métricas de Pipeline")

    reportes_data = run_query(
        "SELECT monto, probabilidad, semana FROM reportes"
    )

    if reportes_data:
      df_fc = pd.DataFrame(reportes_data, columns=["Monto", "Prob", "Semana"])
      df_fc["Forecast_Ponderado"] = df_fc["Monto"] * (df_fc["Prob"] / 100.0)

      total_pipeline = df_fc["Monto"].sum()
      total_forecast = df_fc["Forecast_Ponderado"].sum()

      # Métricas superiores
      m1, m2 = st.columns(2)
      with m1:
        st.markdown(
            f"""
                <div class="metric-card">
                    <div class="metric-value">${total_pipeline:,.2f} MXN</div>
                    <div class="metric-label">Pipeline Total Registrado</div>
                </div>
            """,
            unsafe_allow_html=True,
        )
      with m2:
        st.markdown(
            f"""
                <div class="metric-card">
                    <div class="metric-value" style="color: #16a34a;">${total_forecast:,.2f} MXN</div>
                    <div class="metric-label">Forecast Ponderado Total</div>
                </div>
            """,
            unsafe_allow_html=True,
        )

      st.markdown("---")
      st.markdown("#### 📊 Desglose por Semana Comercial (W1 - W4)")
      df_group = (
          df_fc.groupby("Semana")
          .agg(
              Pipeline_Total=("Monto", "sum"),
              Forecast_Ponderado=("Forecast_Ponderado", "sum"),
              Oportunidades=("Monto", "count"),
          )
          .reset_index()
      )
      st.dataframe(df_group, use_container_width=True, hide_index=True)
    else:
      st.info(
          "Agrega registros en la Bitácora Post-Visita para visualizar el"
          " forecast."
      )

  # ------------------------------------------
  # SUBMÓDULO 4: GENERADOR DE REPORTES
  # ------------------------------------------
  with tab4:
    st.subheader("📄 Generador Automático de Reportes (Correo y Word)")

    clientes_list = run_query("SELECT DISTINCT cliente FROM reportes")
    if clientes_list:
      clientes_opciones = [c[0] for c in clientes_list]
      cliente_sel = st.selectbox(
          "Selecciona el Cliente Registrado", clientes_opciones
      )

      if cliente_sel:
        detalles = run_query(
            "SELECT fecha_rep, pain, monto, probabilidad, semana,"
            " siguiente_paso, proxima_fecha, estatus FROM reportes WHERE"
            " cliente = ? ORDER BY id DESC LIMIT 1",
            (cliente_sel,),
        )
        if detalles:
          d = detalles[0]
          fecha_r, pain_r, monto_r, prob_r, sem_r, paso_r, prox_f, est_r = d

          # Plantilla de Correo
          correo_texto = f"""Estimado equipo directivo / Cliente {cliente_sel}:

Por medio de la presente, compartimos el resumen de nuestra visita de seguimiento técnico-comercial realizada el {fecha_r} (Semana {sem_r}).

- Diagnóstico / Pain detectado: {pain_r}
- Oportunidad Comercial: ${monto_r:,.2f} MXN (Probabilidad de cierre: {prob_r}%)
- Estatus Actual: {est_r}
- Acuerdos / Siguiente Paso: {paso_r} (Próxima fecha: {prox_f})

Quedamos a su entera disposición para continuar impulsando la estrategia metrológica en planta.

Atentamente,
Javier Alfonso Camacho | Asesor Comercial
MESS Servicios Metrológicos
"""

          # Plantilla Markdown / HTML estilizada para Word
          markdown_texto = f"""### REPORTE EJECUTIVO COMERCIAL - MESS SERVICIOS METROLÓGICOS
**Cliente:** {cliente_sel}  
**Fecha de Emisión:** {fecha_r} ({sem_r})  
**Estatus de la Oportunidad:** {est_r}  

---

#### 1. Análisis de Necesidades y Dolores (Pain)
* **Hallazgo Técnico:** {pain_r}

#### 2. Valoración Comercial
* **Monto Estimado:** ${monto_r:,.2f} MXN
* **Probabilidad de Cierre:** {prob_r}%

#### 3. Plan de Acción y Siguiente Paso
* **Acuerdo:** {paso_r}
* **Próximo Seguimiento:** {prox_f}

---
*MESS Servicios Metrológicos • All About Metrology*
"""

          c_col1, c_col2 = st.columns(2)
          with c_col1:
            st.markdown("#### ✉️ Formato Listo para Correo")
            st.text_area(
                "Copia este texto para tu correo:",
                correo_texto,
                height=250,
            )
          with c_col2:
            st.markdown(
                "#### 📄 Formato Ejecutivo (Markdown para Word/Impresión)"
            )
            st.text_area(
                "Copia este bloque para pegar directo en Word:",
                markdown_texto,
                height=250,
            )
    else:
      st.info(
          "Registra al menos una visita y reporte en la bitácora para habilitar"
          " el generador."
      )
