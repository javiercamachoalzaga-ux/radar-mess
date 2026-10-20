import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, date, timedelta
import re
import io
import os
import json
import hmac
import html
import sqlite3
import google.generativeai as genai
import urllib.parse

try:
    from docx import Document
    docx_disponible = True
except ImportError:
    docx_disponible = False

# ============================================================
# CONFIGURACIÓN AJUSTABLE (edita aquí tus reglas de negocio)
# ============================================================
DB_PATH = os.environ.get("SAIV_DB_PATH", "mess_radar.db")
META_MENSUAL_USD = 80000.00
META_CUENTAS_CLAVE = 40

FASES = ["1. Propuesta", "2. Cotización", "3. Negociación", "4. Esperando PO", "5. Cerrado Ganado", "6. Perdido"]

# Probabilidad por defecto según fase (puedes calibrarla con tu historial real)
PROB_FASE = {
    "1. Propuesta": 15,
    "2. Cotización": 30,
    "3. Negociación": 60,
    "4. Esperando PO": 90,
    "5. Cerrado Ganado": 100,
    "6. Perdido": 0,
}

# Días sin movimiento para considerar un proyecto estancado, por fase
UMBRAL_DIAS = {
    "1. Propuesta": 15,
    "2. Cotización": 15,
    "3. Negociación": 10,
    "4. Esperando PO": 7,
}

# Escenarios del ROI: % de rechazos que el equipo logra eliminar
ESCENARIOS_ROI = {"Conservador": 0.50, "Base": 0.75, "Optimista": 1.00}


def rango_fase(fase):
    """Número de la fase ('3. Negociación' -> 3). Sirve para comparar avance."""
    m = re.match(r"\s*(\d+)", str(fase))
    return int(m.group(1)) if m else 0


def esc(texto):
    """Escapa texto antes de inyectarlo en HTML."""
    return html.escape(str(texto), quote=True)


# 1. Blindaje de ícono e imágenes locales
icono_pag = "logo mess 1.jpg" if os.path.exists("logo mess 1.jpg") else "📊"

st.set_page_config(
    page_title="SAIV | Radar Comercial MESS",
    page_icon=icono_pag,
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif !important; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    :root { --mess-blue: #003a70; --mess-dark: #2c3e50; --mess-light: #f8fafc; }
    .titulo-radar { font-size: 36px; font-weight: 900; color: var(--mess-blue); margin-bottom: -5px; letter-spacing: -1px; text-transform: uppercase; }
    .subtitulo { font-size: 14px; color: #64748b; margin-bottom: 30px; font-weight: 600; text-transform: uppercase; }
    div[data-testid="metric-container"] { background-color: #ffffff; border: 1px solid #e2e8f0; padding: 15px 20px; border-radius: 8px; border-left: 5px solid var(--mess-blue); box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; font-weight: 700 !important; color: #64748b !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { font-size: 24px !important; font-weight: 800 !important; color: var(--mess-dark) !important; }
    .alerta-estancado { background: #fff1f2; border-left: 5px solid #e11d48; padding: 15px; border-radius: 6px; margin-bottom: 5px; }
    .stButton>button { font-weight: 600; border-radius: 6px; }
    .caja-ia { background-color: #fefefe; padding: 15px; border-radius: 5px; border-left: 4px solid #3498db; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}
    .caja-abm { background-color: #f8fafc; padding: 15px; border-radius: 5px; border-left: 4px solid #8b5cf6; margin-bottom: 15px; border: 1px solid #e2e8f0;}
    .btn-google { background-color: #4285F4; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 5px; text-align: center; width: 100%; }
    .btn-wa { background-color: #25D366; color: white !important; text-decoration: none; padding: 10px 15px; border-radius: 5px; font-weight: bold; display: inline-block; margin-top: 5px; text-align: center; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

col_logo, col_titulos = st.columns([1, 10])
with col_logo:
    if os.path.exists("logo mess 1.jpg"):
        st.image("logo mess 1.jpg", width=80)
with col_titulos:
    st.markdown('<div class="titulo-radar" style="margin-top: -10px;">SAIV | Sistema Automatizado de Ingeniería de Ventas</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitulo">Módulo CRM SCOTT | Revenue Operations | MESS</div>', unsafe_allow_html=True)


def check_password():
    """Falla cerrado: sin contraseña configurada NO se da acceso (salvo modo local explícito)."""
    try:
        hay_password = "mi_contrasena" in st.secrets
    except Exception:
        hay_password = False

    if not hay_password:
        if os.environ.get("SAIV_MODO_ABIERTO") == "1":
            return True
        st.error("Acceso bloqueado: falta configurar 'mi_contrasena' en Secrets. "
                 "Para pruebas locales puedes definir la variable de entorno SAIV_MODO_ABIERTO=1.")
        return False

    if st.session_state.get("autenticado", False):
        return True

    st.markdown("---")
    st.markdown("### Acceso Restringido")
    with st.form("login_form"):
        pwd = st.text_input("Ingresa tu contraseña corporativa", type="password")
        btn_acceder = st.form_submit_button("Acceder al SAIV")

    if btn_acceder:
        esperado = str(st.secrets["mi_contrasena"]).encode("utf-8")
        if hmac.compare_digest(pwd.encode("utf-8"), esperado):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta. Intenta de nuevo.")
    return False


if not check_password():
    st.stop()

if os.path.exists("logo mess 2.jpg"):
    st.sidebar.image("logo mess 2.jpg", use_container_width=True)

try:
    if "gemini_api_key" in st.secrets:
        genai.configure(api_key=st.secrets["gemini_api_key"])
        gemini_activo = True
    else:
        gemini_activo = False
except Exception:
    gemini_activo = False

# Variables de estado
vars_txt = ['ai_analisis', 'ai_mensaje', 'ai_objeciones', 'ai_marketing', 'ai_log',
            'ai_cliente', 'ai_folio', 'roi_calc', 'ai_origen', 'ai_fase']
for v in vars_txt:
    if v not in st.session_state:
        st.session_state[v] = ""
for nv in ['ai_usd', 'ai_mxn', 'roi_meses_num']:
    if nv not in st.session_state:
        st.session_state[nv] = 0.0
if 'roi_tabla' not in st.session_state:
    st.session_state['roi_tabla'] = []


# ============================================================
# BASE DE DATOS
# ============================================================
def run_query(query, params=(), fetch=True):
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(query, params)
        if fetch:
            return cursor.fetchall()
        conn.commit()
    finally:
        conn.close()


def init_db():
    run_query("""
        CREATE TABLE IF NOT EXISTS reportes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_proyecto TEXT,
            cliente TEXT,
            pain TEXT,
            monto REAL,
            probabilidad INTEGER,
            semana TEXT,
            divisa TEXT,
            siguiente_paso TEXT,
            fecha_prox TEXT,
            estatus TEXT,
            roi_calculado REAL,
            ultimo_contacto TEXT
        )
    """, fetch=False)
    columnas = [col[1] for col in run_query("PRAGMA table_info(reportes)")]
    if 'folio_proyecto' not in columnas:
        run_query("ALTER TABLE reportes ADD COLUMN folio_proyecto TEXT", fetch=False)
    if 'divisa' not in columnas:
        run_query("ALTER TABLE reportes ADD COLUMN divisa TEXT DEFAULT 'MXN'", fetch=False)
    if 'fecha_prox' not in columnas:
        run_query("ALTER TABLE reportes ADD COLUMN fecha_prox TEXT", fetch=False)
    if 'roi_calculado' not in columnas:
        run_query("ALTER TABLE reportes ADD COLUMN roi_calculado REAL", fetch=False)
    if 'ultimo_contacto' not in columnas:
        run_query("ALTER TABLE reportes ADD COLUMN ultimo_contacto TEXT", fetch=False)


init_db()


def upsert_forecast(folio, cliente, pain, monto, prob, semana, divisa, sig_paso, fecha_prox, estatus, roi_val):
    """Inserta o actualiza. Una actualización solo adelanta la fase; nunca la retrocede
    ni pisa la probabilidad que ya hayas ajustado a mano en el Forecast."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    existente = run_query(
        "SELECT id, estatus FROM reportes WHERE folio_proyecto = ? AND divisa = ?", (folio, divisa)
    )
    if existente:
        id_reg, est_previo = existente[0]
        if rango_fase(estatus) > rango_fase(est_previo):
            run_query(
                """UPDATE reportes
                   SET cliente=?, pain=?, monto=?, siguiente_paso=?, fecha_prox=?,
                       estatus=?, probabilidad=?, roi_calculado=?, ultimo_contacto=?
                   WHERE id=?""",
                (cliente, pain, monto, sig_paso, fecha_prox, estatus, prob, roi_val, hoy, id_reg),
                fetch=False
            )
        else:
            run_query(
                """UPDATE reportes
                   SET cliente=?, pain=?, monto=?, siguiente_paso=?, fecha_prox=?,
                       roi_calculado=?, ultimo_contacto=?
                   WHERE id=?""",
                (cliente, pain, monto, sig_paso, fecha_prox, roi_val, hoy, id_reg),
                fetch=False
            )
    else:
        run_query(
            """INSERT INTO reportes
               (folio_proyecto, cliente, pain, monto, probabilidad, semana, divisa,
                siguiente_paso, fecha_prox, estatus, roi_calculado, ultimo_contacto)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (folio, cliente, pain, monto, prob, semana, divisa, sig_paso, fecha_prox, estatus, roi_val, hoy),
            fetch=False
        )


# ============================================================
# IA (Gemini) con salida JSON estructurada
# ============================================================
def a_texto(valor):
    if valor is None:
        return "Sin datos."
    if isinstance(valor, (list, tuple)):
        return "\n".join(f"- {a_texto(v)}" if not isinstance(v, str) else f"- {v}" for v in valor)
    if isinstance(valor, dict):
        return "\n".join(f"{k}: {a_texto(v)}" for k, v in valor.items())
    return str(valor).strip() or "Sin datos."


def parsear_json_ia(texto):
    limpio = re.sub(r'^```[a-zA-Z]*\s*|\s*```$', '', texto.strip())
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', limpio, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def ejecutar_ia(cliente, interlocutor, num_proy, eqs, t_usd, t_mxn, obj_tactico, canal, contexto,
                fase="", dias=None):
    roi_info = f" Argumento financiero ROI disponible: {st.session_state.roi_calc}." if st.session_state.get('roi_calc') else ""
    fase_info = f" Fase actual del pipeline: {fase}." if fase else ""
    dias_info = f" Días sin movimiento: {dias}." if dias is not None else ""
    prompt = (
        f"Eres Javier Camacho, KAM en MESS Servicios Metrológicos. "
        f"Cliente: {cliente} (Interlocutor: {interlocutor}). Proyectos agrupados: {num_proy}. "
        f"Equipos/Servicios: {eqs}. Monto: ${t_usd:,.2f} USD / ${t_mxn:,.2f} MXN.{fase_info}{dias_info} "
        f"Objetivo Estratégico: {obj_tactico}. Modalidad / Canal de Acción: {canal}. "
        f"Contexto táctico: {contexto}.{roi_info} "
        f"Si la acción incluye Visita con Acompañamiento o Director, estructura el plan considerando el rol ejecutivo de respaldo gerencial/directivo para destrabar o cerrar la cuenta. "
        f"Fusiona MEDDPICC, SPIN y Sandler de forma invisible, tono humano, conversacional y directo B2B, sin exagerar tecnicismos. "
        f"Responde ÚNICAMENTE con un objeto JSON válido (sin Markdown) con exactamente estas llaves, todas con valor de texto: "
        f'"analisis" (análisis estratégico para "{obj_tactico}" y cómo vender el paquete), '
        f'"mensaje" (el texto o guion exacto para {canal}), '
        f'"objeciones" (2 posibles objeciones y cómo rebatirlas), '
        f'"marketing" (solicitud concreta de Account-Based Marketing para esta cuenta), '
        f'"bitacora" (bitácora hiper-resumida de 2 líneas para el CRM SCOTT).'
    )

    res = ""
    last_err = None
    for mod_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        try:
            model = genai.GenerativeModel(
                mod_name,
                generation_config={"response_mime_type": "application/json"}
            )
            res = model.generate_content(prompt).text
            break
        except Exception as e:
            last_err = e
            continue
    if not res:
        raise RuntimeError(f"No se pudo conectar con el modelo de Gemini: {last_err}")

    datos = parsear_json_ia(res)
    return {
        'ai_analisis': a_texto(datos.get('analisis')),
        'ai_mensaje': a_texto(datos.get('mensaje')),
        'ai_objeciones': a_texto(datos.get('objeciones')),
        'ai_marketing': a_texto(datos.get('marketing')),
        'ai_log': a_texto(datos.get('bitacora')),
    }


def mostrar_resultados_ia(canal_actual="Seguimiento"):
    # Solo muestra los resultados en la pestaña que los originó
    if st.session_state.get('ai_mensaje') and st.session_state.get('ai_origen') == canal_actual:
        st.success(f"Estrategia Generada para: {st.session_state.ai_cliente} (Folios: {st.session_state.ai_folio})")
        st.info(f"**1. Análisis Estratégico (Bundle):**\n\n{st.session_state.ai_analisis}")

        msj_formateado = esc(st.session_state.ai_mensaje).replace('\n', '<br>')
        st.markdown(f"<div class='caja-ia'><b>2. Mensaje / Guion de Contacto:</b><br><br>{msj_formateado}</div>",
                    unsafe_allow_html=True)

        st.warning(f"**3. Manejo de Objeciones:**\n\n{st.session_state.ai_objeciones}")

        abm_formateado = esc(st.session_state.ai_marketing).replace('\n', '<br>')
        st.markdown(f"<div class='caja-abm'><b>4. Solicitud Account-Based Marketing (ABM):</b><br><br>{abm_formateado}</div>",
                    unsafe_allow_html=True)

        st.divider()
        st.markdown("### Módulo de Ejecución Rápida")
        c_op1, c_op2, c_op3 = st.columns(3)

        with c_op1:
            txt_wa = urllib.parse.quote(st.session_state.ai_mensaje)
            url_wa = f"https://wa.me/?text={txt_wa}"
            st.markdown(f'<a href="{url_wa}" target="_blank" class="btn-wa">Enviar por WhatsApp</a>', unsafe_allow_html=True)
            st.caption("Abre WhatsApp con el mensaje listo.")

        with c_op2:
            titulo_cita = urllib.parse.quote(f"Visita / Seguimiento MESS - {st.session_state.ai_cliente}")
            detalles_cita = urllib.parse.quote(f"Folios: {st.session_state.ai_folio}\n\nBitácora:\n{st.session_state.ai_log}")
            url_gcal = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={titulo_cita}&details={detalles_cita}"
            st.markdown(f'<a href="{url_gcal}" target="_blank" class="btn-google">Agendar en Calendar</a>', unsafe_allow_html=True)
            st.caption("Crea el recordatorio en tu calendario.")

        with c_op3:
            if docx_disponible:
                def generar_docx():
                    doc = Document()
                    doc.add_heading("PLAN DE ATAQUE KAM - MESS", 0)
                    doc.add_paragraph(f"Cliente: {st.session_state.ai_cliente} | Folios: {st.session_state.ai_folio}")
                    doc.add_heading("1. Análisis Estratégico", 1)
                    doc.add_paragraph(st.session_state.ai_analisis)
                    doc.add_heading("2. Guion / Mensaje", 1)
                    doc.add_paragraph(st.session_state.ai_mensaje)
                    doc.add_heading("3. Objeciones", 1)
                    doc.add_paragraph(st.session_state.ai_objeciones)
                    doc.add_heading("4. Solicitud ABM", 1)
                    doc.add_paragraph(st.session_state.ai_marketing)
                    b = io.BytesIO()
                    doc.save(b)
                    b.seek(0)
                    return b
                st.download_button(
                    "Descargar Ficha .docx",
                    data=generar_docx(),
                    file_name=f"Plan_{st.session_state.ai_cliente.replace(' ', '_')}.docx",
                    use_container_width=True,
                    key=f"docx_{canal_actual}"
                )

        st.markdown("**5. Bitácora Hiper-Resumida (Copia y pega en SCOTT CRM):**")
        st.text_area("Reporte listo para SCOTT:", value=st.session_state.ai_log, height=90, key=f"scott_{canal_actual}")

        fase_iny = st.session_state.get('ai_fase') or "1. Propuesta"
        prob_iny = PROB_FASE.get(fase_iny, 15)
        f_prox = st.date_input(
            "Fecha de la próxima acción:",
            value=date.today() + timedelta(days=3),
            key=f"fprox_{canal_actual}"
        )
        st.caption(f"Se registrará en la fase real del CRM ({fase_iny}) con probabilidad inicial de {prob_iny}%. "
                   f"Puedes ajustarla después en la pestaña de Forecast.")

        if st.button("Inyectar al Forecast del SAIV", key=f"iny_{canal_actual}", type="primary"):
            roi_val = float(st.session_state.get('roi_meses_num', 0.0))
            fecha_txt = f_prox.strftime("%Y-%m-%d")
            inyectado = False

            # Soporte bimoneda sin pérdida de datos y evitando duplicados (Upsert)
            for divisa, monto in (("USD", st.session_state.ai_usd), ("MXN", st.session_state.ai_mxn)):
                if monto > 0:
                    upsert_forecast(
                        st.session_state.ai_folio, st.session_state.ai_cliente, st.session_state.ai_log,
                        monto, prob_iny, "W1", divisa, canal_actual, fecha_txt, fase_iny, roi_val
                    )
                    inyectado = True
            if not inyectado:
                upsert_forecast(
                    st.session_state.ai_folio, st.session_state.ai_cliente, st.session_state.ai_log,
                    0.0, prob_iny, "W1", "MXN", canal_actual, fecha_txt, fase_iny, roi_val
                )
            st.success("Proyecto registrado / actualizado en el Forecast sin duplicados.")


# ============================================================
# PROCESAMIENTO DEL CSV (cacheado por contenido del archivo)
# ============================================================
@st.cache_data(show_spinner=False)
def procesar_csv(contenido: bytes, modo_monto: str = "sumar"):
    """Devuelve (DataFrame | None, lista_de_avisos, mensaje_de_error | None)."""
    avisos = []
    try:
        df_raw = pd.read_csv(io.BytesIO(contenido), encoding='latin-1', header=None, sep=None, engine='python')
        header_idx = -1
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(x).upper() for x in row.dropna()]).strip()
            if 'PROYECTO' in row_str and 'CLIENTE' in row_str:
                header_idx = idx
                break
        if header_idx == -1:
            return None, avisos, "No se encontró la fila de encabezados (se esperan las columnas PROYECTO y CLIENTE)."

        # Alineación exacta de encabezados con sus respectivas columnas
        raw_headers = df_raw.iloc[header_idx]
        valid_cols = [i for i, val in enumerate(raw_headers) if pd.notna(val) and str(val).strip() != '']
        headers = [str(raw_headers.iloc[i]).upper().replace('\ufeff', '').strip() for i in valid_cols]

        df_data = df_raw.iloc[header_idx + 1:, valid_cols].copy()
        df_data.columns = headers
        df_data = df_data.dropna(axis=0, how='all').reset_index(drop=True)

        def buscar_col(claves):
            for clave in claves:
                for col in df_data.columns:
                    if str(col).upper().strip() == clave or str(col).upper().strip() == f"{clave}.1":
                        col_data = df_data[col]
                        if isinstance(col_data, pd.DataFrame):
                            return col_data.iloc[:, 0].copy()
                        return col_data.copy()
            return pd.Series([None] * len(df_data))

        df_clean = pd.DataFrame()
        df_clean['ID_Proyecto'] = buscar_col(["PROYECTO", "FOLIO"])
        df_clean['Cliente'] = buscar_col(["CLIENTE", "EMPRESA"])
        df_clean['Area'] = buscar_col(["AREA", "ÁREA"])
        df_clean['Fecha_Creacion'] = buscar_col(["FECHA DE REGISTRO", "FECHA"])
        df_clean['Estatus_CRM'] = buscar_col(["ESTATUS"])
        df_clean['Etapa'] = buscar_col(["ETAPA", "FASE"])
        df_clean['Descripcion'] = buscar_col(["DESCRIPCION", "DESCRIPCIÓN"])

        # --- Montos: una sola columna por moneda para evitar doble conteo ---
        n = len(df_data)
        col_moneda = buscar_col(["MONEDA", "DIVISA"])
        mon_fila = col_moneda.astype(str).str.upper().to_numpy()
        mon_fila_usd = np.array(['USD' in x for x in mon_fila])

        PRIORIDAD = ["VALOR", "MONTO", "IMPORTE", "TOTAL"]
        elegidas = {}      # bucket ('USD' | 'MXN') -> (idx_columna, clave)
        ignoradas = []
        for col_idx, col_name in enumerate(df_data.columns):
            c_name = str(col_name).upper().strip()
            clave = next((k for k in PRIORIDAD if k in c_name), None)
            if clave is None:
                continue
            bucket = 'USD' if ('USD' in c_name or 'US$' in c_name) else 'MXN'
            actual = elegidas.get(bucket)
            if actual is None:
                elegidas[bucket] = (col_idx, clave)
            elif PRIORIDAD.index(clave) < PRIORIDAD.index(actual[1]):
                ignoradas.append(df_data.columns[actual[0]])
                elegidas[bucket] = (col_idx, clave)
            else:
                ignoradas.append(col_name)
        if ignoradas:
            avisos.append("Columnas de monto ignoradas para evitar doble conteo: " + ", ".join(map(str, ignoradas)))

        monto_mxn, monto_usd = np.zeros(n), np.zeros(n)
        for bucket, (col_idx, _) in elegidas.items():
            texto = df_data.iloc[:, col_idx].astype(str).str.upper()
            nums = (texto.str.replace(',', '', regex=False)
                    .str.extract(r'(\d+(?:\.\d+)?)')[0].astype(float).fillna(0.0).to_numpy())
            marca_usd = texto.str.contains(r'USD|US\$', regex=True).to_numpy()
            es_usd = np.logical_or(np.logical_or(bucket == 'USD', marca_usd), mon_fila_usd)
            monto_usd += np.where(es_usd, nums, 0.0)
            monto_mxn += np.where(es_usd, 0.0, nums)

        df_clean['Monto_MXN'] = monto_mxn
        df_clean['Monto_USD'] = monto_usd
        df_clean = df_clean.dropna(subset=['ID_Proyecto']).reset_index(drop=True)
        df_clean['Cliente'] = df_clean['Cliente'].apply(
            lambda x: re.sub(r'\s+', ' ', str(x).replace("?", "ó")).strip().title() if pd.notna(x) else "")
        df_clean['Cliente_Maestro'] = df_clean['Cliente'].str.upper()
        df_clean['Cliente_Final'] = df_clean.groupby('ID_Proyecto')['Cliente_Maestro'].transform(
            lambda x: x.replace("", np.nan).ffill().bfill())
        df_clean['Cliente_Final'] = df_clean['Cliente_Final'].fillna("POR ASIGNAR / SIN CLIENTE")

        # Aviso si el CRM parece repetir el total en cada línea del folio
        if modo_monto == "sumar":
            multi = df_clean.groupby('ID_Proyecto').agg(
                n=('Monto_USD', 'size'),
                u_usd=('Monto_USD', 'nunique'), u_mxn=('Monto_MXN', 'nunique'),
                m_usd=('Monto_USD', 'max'), m_mxn=('Monto_MXN', 'max'))
            repetidos = multi[(multi['n'] > 1) & (multi['u_usd'] <= 1) & (multi['u_mxn'] <= 1)
                              & ((multi['m_usd'] > 0) | (multi['m_mxn'] > 0))]
            if len(repetidos) > 0:
                avisos.append(f"{len(repetidos)} folios tienen varias líneas con el mismo monto. "
                              f"Si el CRM repite el total en cada línea, cambia a 'Máximo por folio' en la barra lateral.")

        fn_monto = 'sum' if modo_monto == "sumar" else 'max'
        df_agrupado = df_clean.groupby('ID_Proyecto').agg({
            'Cliente_Final': 'first', 'Area': 'first', 'Fecha_Creacion': 'first',
            'Estatus_CRM': 'first', 'Etapa': 'first',
            'Descripcion': lambda x: ' | '.join([str(i) for i in x.dropna().unique() if str(i).strip() != ""]),
            'Monto_MXN': fn_monto, 'Monto_USD': fn_monto
        }).reset_index()

        df_agrupado.rename(columns={'Cliente_Final': 'Cliente'}, inplace=True)
        df_agrupado = df_agrupado[(df_agrupado['Monto_MXN'] > 0) | (df_agrupado['Monto_USD'] > 0)]

        filtro_estatus = df_agrupado['Estatus_CRM'].astype(str).str.contains('PROCESO', case=False, na=False)
        filtro_etapa = df_agrupado['Etapa'].astype(str).str.contains(
            r'PROPUESTA|COTIZACI|NEGOCIACI|\bPO\b|ORDEN', regex=True, case=False, na=False)
        df_agrupado = df_agrupado[filtro_estatus | filtro_etapa].copy()

        def clasificar_pilar(row):
            texto = (str(row['Area']) + " " + str(row['Descripcion'])).upper()
            claves_ag = ["ALTA GAMA", "CMM", "SCANNER", "ÓPTICO", "OPTICO", "BRAZO", "ZEISS", "BATY", "KREON", "VICIVISION", "SCANTECH"]
            claves_cal = ["CALIBRACIÓN", "CALIBRACION", "LABORATORIO", "DIMENSIONAL"]
            if any(k in texto for k in claves_ag):
                return "1. Alta Gama"
            elif any(k in texto for k in claves_cal):
                return "2. Calibraciones"
            else:
                return "3. Productos Generales"

        df_agrupado['Pilar_Estrategico'] = df_agrupado.apply(clasificar_pilar, axis=1)

        def clasificar_fase(etapa):
            e = str(etapa).upper()
            if re.search(r'PERDID|CANCEL|POSPUEST', e):
                return "6. Perdido"
            elif 'GANAD' in e or 'CERRAD' in e:
                return "5. Cerrado Ganado"
            elif re.search(r'\bPO\b|ORDEN|ESPERANDO', e):
                return "4. Esperando PO"
            elif 'NEGOCIACI' in e:
                return "3. Negociación"
            elif 'COTIZACI' in e:
                return "2. Cotización"
            else:
                return "1. Propuesta"

        df_agrupado['Fase_Pipeline'] = df_agrupado['Etapa'].apply(clasificar_fase)

        # Fechas inválidas quedan como NaN (NO se tratan como "0 días")
        df_agrupado['Fecha_Creacion_DT'] = pd.to_datetime(df_agrupado['Fecha_Creacion'], errors='coerce', dayfirst=True)
        sin_fecha = int(df_agrupado['Fecha_Creacion_DT'].isna().sum())
        if sin_fecha:
            avisos.append(f"{sin_fecha} folios no tienen una fecha de registro válida; no se pueden evaluar como estancados.")

        return df_agrupado, avisos, None
    except Exception as e:
        return None, avisos, f"Error procesando CSV: {e}"


def sync_master_key(df_csv):
    """Cruza el CSV con SQLite. Gana la fase más avanzada entre CRM y SAIV, y agrega
    probabilidad efectiva y días sin movimiento (desde el último contacto o la creación)."""
    if df_csv.empty:
        return df_csv
    df_csv = df_csv.copy()
    df_csv['ID_Proyecto'] = df_csv['ID_Proyecto'].astype(str)

    db_reps = run_query(
        "SELECT folio_proyecto, estatus, probabilidad, ultimo_contacto FROM reportes WHERE folio_proyecto IS NOT NULL"
    ) or []
    registros = []
    for folio_str, est, prob, ult in db_reps:
        for f_ind in str(folio_str).split(","):
            f_limpio = f_ind.strip()
            if f_limpio:
                registros.append((f_limpio, est, prob, ult))

    df_db = pd.DataFrame(registros, columns=['ID_Proyecto', 'Estatus_RevOps', 'Probabilidad_RevOps', 'Ultimo_Contacto'])
    if not df_db.empty:
        df_db['ID_Proyecto'] = df_db['ID_Proyecto'].astype(str)
        df_db['Ultimo_Contacto'] = pd.to_datetime(df_db['Ultimo_Contacto'], errors='coerce')
        df_db['_rango'] = df_db['Estatus_RevOps'].map(rango_fase)
        df_db = (df_db.sort_values(['ID_Proyecto', '_rango', 'Ultimo_Contacto'])
                 .drop_duplicates('ID_Proyecto', keep='last').drop(columns='_rango'))

    df_m = df_csv.merge(df_db, on='ID_Proyecto', how='left')
    df_m['Ultimo_Contacto'] = pd.to_datetime(df_m['Ultimo_Contacto'], errors='coerce')
    df_m['Probabilidad_RevOps'] = pd.to_numeric(df_m['Probabilidad_RevOps'], errors='coerce')

    rango_crm = df_m['Fase_Pipeline'].map(rango_fase)
    rango_db = df_m['Estatus_RevOps'].map(rango_fase)
    usar_db = df_m['Estatus_RevOps'].notna() & (rango_db >= rango_crm)

    df_m['Fase_Pipeline'] = np.where(usar_db, df_m['Estatus_RevOps'], df_m['Fase_Pipeline'])
    prob_default = df_m['Fase_Pipeline'].map(PROB_FASE).fillna(15)
    df_m['Prob_Efectiva'] = np.where(
        usar_db & df_m['Probabilidad_RevOps'].notna(), df_m['Probabilidad_RevOps'], prob_default
    ).astype(float)

    ref = df_m[['Fecha_Creacion_DT', 'Ultimo_Contacto']].max(axis=1)
    df_m['Días_Sin_Mov'] = (pd.Timestamp.now().normalize() - ref).dt.days
    return df_m


# ============================================================
# BARRA LATERAL Y CARGA DE ARCHIVO
# ============================================================
st.sidebar.header("Configuración")
modo_label = st.sidebar.radio(
    "Monto por folio cuando hay varias líneas:",
    ["Sumar líneas", "Máximo por folio (el CRM repite el total)"]
)
modo_monto = "sumar" if modo_label.startswith("Sumar") else "maximo"
tc = st.sidebar.number_input("Tipo de cambio (MXN por 1 USD)", min_value=1.0, value=18.0, step=0.1,
                             help="Se usa para consolidar MXN a USD equivalente. Ajústalo al TC vigente.")

if os.path.exists(DB_PATH):
    with open(DB_PATH, "rb") as fh:
        st.sidebar.download_button("Respaldar base de datos (.db)", data=fh.read(),
                                   file_name="mess_radar_respaldo.db", use_container_width=True)

archivo = st.file_uploader("Sube la extracción del CRM (CSV)", type=["csv"])
df = pd.DataFrame()

if archivo:
    df_bruto, avisos_csv, error_csv = procesar_csv(archivo.getvalue(), modo_monto)
    if error_csv:
        st.error(error_csv)
    for aviso in avisos_csv:
        st.warning(aviso)
    if df_bruto is not None and not df_bruto.empty:
        df_completo = sync_master_key(df_bruto)
        df = df_completo[df_completo['Fase_Pipeline'] != "6. Perdido"].copy()
        st.sidebar.divider()
        st.sidebar.header("Filtros Directivos")
        f_pilar = st.sidebar.multiselect("Pilar Estratégico:", sorted(df['Pilar_Estrategico'].unique()),
                                         default=sorted(df['Pilar_Estrategico'].unique()))
        f_buscar = st.sidebar.text_input("Buscar Folio o Cliente:")
        if f_buscar:
            df = df[(df['ID_Proyecto'].astype(str).str.contains(f_buscar, case=False, na=False, regex=False)) |
                    (df['Cliente'].astype(str).str.contains(f_buscar, case=False, na=False, regex=False))]
        if f_pilar:
            df = df[df['Pilar_Estrategico'].isin(f_pilar)]

t_dash, t_stalled, t_ai, t_revops = st.tabs([
    "1. Dashboards CRM",
    "2. Proyectos Estancados",
    "3. Laboratorio Táctico IA",
    "4. Gestión Comercial (RevOps)"
])

# ============================================================
# 1. DASHBOARDS
# ============================================================
with t_dash:
    if not df.empty:
        df['USD_Eq'] = df['Monto_USD'] + df['Monto_MXN'] / tc
        df['Pond_USD'] = df['USD_Eq'] * df['Prob_Efectiva'] / 100.0

        df_caliente = df[df['Fase_Pipeline'].isin(['3. Negociación', '4. Esperando PO', '5. Cerrado Ganado'])]
        usd_caliente = df_caliente['Monto_USD'].sum()
        mxn_caliente = df_caliente['Monto_MXN'].sum()
        bruto_eq = df['USD_Eq'].sum()
        ponderado = df['Pond_USD'].sum()
        cuentas_activas = df['Cliente'].nunique()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Meta Mensual (USD)", f"${META_MENSUAL_USD:,.0f}")
        c2.metric("Pipeline Caliente (bruto)", f"${usd_caliente:,.0f} USD", f"+ ${mxn_caliente:,.0f} MXN", delta_color="off")
        c3.metric("Pipeline Ponderado (USD eq.)", f"${ponderado:,.0f}", f"Bruto total: ${bruto_eq:,.0f}", delta_color="off")
        gap = META_MENSUAL_USD - ponderado
        if gap > 0:
            c4.metric("GAP vs. Ponderado", f"${gap:,.0f} USD", "- Acción Requerida")
        else:
            c4.metric("GAP vs. Ponderado", "$0 USD", "+ Meta Cubierta")
        c5.metric("Cuentas con Pipeline", f"{cuentas_activas}", f"Meta: {META_CUENTAS_CLAVE} cuentas clave", delta_color="off")
        st.caption(f"Ponderado = monto × probabilidad por folio. MXN convertido a USD con TC {tc:,.2f}. "
                   f"El pipeline caliente suma Negociación, Esperando PO y Cerrado Ganado sin ponderar.")

        st.divider()
        moneda_sel = st.radio("Moneda de Análisis:", ["USD", "MXN"], horizontal=True)
        col_val = 'Monto_USD' if moneda_sel == "USD" else 'Monto_MXN'

        st.markdown(f"#### Análisis Pareto 80/20 por Cuentas ({moneda_sel})")
        df_pareto = df.groupby('Cliente')[col_val].sum().reset_index()
        df_pareto = df_pareto[df_pareto[col_val] > 0].sort_values(by=col_val, ascending=False).reset_index(drop=True)
        if not df_pareto.empty:
            df_pareto['Porcentaje'] = df_pareto[col_val] / df_pareto[col_val].sum()
            df_pareto['Acumulado'] = df_pareto['Porcentaje'].cumsum()
            barras = alt.Chart(df_pareto).mark_bar(color='#003a70').encode(x=alt.X('Cliente', sort=None), y=alt.Y(col_val))
            linea = alt.Chart(df_pareto).mark_line(color='#e74c3c', point=True).encode(
                x=alt.X('Cliente', sort=None), y=alt.Y('Acumulado', axis=alt.Axis(format='%')))
            st.altair_chart(alt.layer(barras, linea).resolve_scale(y='independent').properties(height=350), use_container_width=True)

        cg1, cg2 = st.columns(2)
        with cg1:
            st.markdown("**Forecast por Área**")
            df_a = df.groupby('Area')[col_val].sum().reset_index()
            if not df_a.empty:
                st.altair_chart(alt.Chart(df_a).mark_bar(color='#2c3e50').encode(
                    x=col_val, y=alt.Y('Area', sort='-x')).properties(height=300), use_container_width=True)
        with cg2:
            st.markdown("**Salud del Embudo**")
            df_f = df.groupby('Fase_Pipeline')[col_val].sum().reset_index()
            if not df_f.empty:
                st.altair_chart(alt.Chart(df_f).mark_bar(color='#16a34a').encode(
                    x=col_val, y=alt.Y('Fase_Pipeline', sort='-x')).properties(height=300), use_container_width=True)
    else:
        st.info("Sube el archivo CSV del CRM para visualizar los dashboards.")

# ============================================================
# 2. PROYECTOS ESTANCADOS
# ============================================================
with t_stalled:
    if not df.empty:
        st.subheader("Riesgo Operativo: Proyectos sin movimiento")
        st.caption("Umbrales por fase: " + " | ".join(f"{f.split('. ')[1]}: {d} días" for f, d in UMBRAL_DIAS.items())
                   + ". Se mide desde el último contacto registrado en SAIV o, si no hay, desde la fecha de registro.")

        umbral = df['Fase_Pipeline'].map(UMBRAL_DIAS)
        estancados = df[umbral.notna() & (df['Días_Sin_Mov'] > umbral)].sort_values(by='Días_Sin_Mov', ascending=False)
        sin_fecha = df[umbral.notna() & df['Días_Sin_Mov'].isna()]

        if not estancados.empty:
            for idx_st, r in estancados.iterrows():
                dias_r = int(r['Días_Sin_Mov'])
                c_al1, c_al2 = st.columns([4, 1])
                with c_al1:
                    alerta_txt = (
                        f'<div class="alerta-estancado">'
                        f'<h4 style="margin:0; color:#9f1239;">Folio: {esc(r["ID_Proyecto"])} | {esc(r["Cliente"])}</h4>'
                        f'<p style="margin:5px 0 0 0; font-size:13px;"><b>Fase:</b> {esc(r["Fase_Pipeline"])} | '
                        f'<b>Días sin movimiento:</b> {dias_r} | '
                        f'<b>Monto:</b> ${r["Monto_USD"]:,.2f} USD / ${r["Monto_MXN"]:,.2f} MXN | '
                        f'<b>Alcance:</b> {esc(str(r["Descripcion"])[:90])}...</p>'
                        f'</div>'
                    )
                    st.markdown(alerta_txt, unsafe_allow_html=True)
                with c_al2:
                    st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
                    if st.button("Generar Rescate", key=f"resc_{r['ID_Proyecto']}_{idx_st}", use_container_width=True):
                        if gemini_activo:
                            with st.spinner(f"Creando rescate Sandler para {r['Cliente']}..."):
                                try:
                                    ctx_resc = (f"Proyecto sin movimiento hace {dias_r} días en etapa {r['Fase_Pipeline']}. "
                                                f"Aplica técnica de desarme de Sandler (cierre negativo suave) para que el cliente "
                                                f"revele si el proyecto sigue vivo o si hay un bloqueo oculto.")
                                    datos_ia = ejecutar_ia(
                                        r['Cliente'], "Comprador / Ingeniero", 1, r['Descripcion'],
                                        r['Monto_USD'], r['Monto_MXN'], "Rescate / Desbloqueo de Negociación",
                                        "Mensaje WhatsApp / Correo de Rescate", ctx_resc,
                                        fase=r['Fase_Pipeline'], dias=dias_r
                                    )
                                    st.session_state.update(datos_ia)
                                    st.session_state.update({
                                        'ai_cliente': r['Cliente'],
                                        'ai_folio': str(r['ID_Proyecto']),
                                        'ai_usd': float(r['Monto_USD']),
                                        'ai_mxn': float(r['Monto_MXN']),
                                        'ai_fase': r['Fase_Pipeline'],
                                        'ai_origen': "Rescate_Estancado"
                                    })
                                except Exception as e:
                                    st.error(f"Error API: {e}")
                        else:
                            st.error("Configura tu API Key de Gemini en Secrets.")

            if st.session_state.get('ai_mensaje') and st.session_state.get('ai_origen') == "Rescate_Estancado":
                st.divider()
                mostrar_resultados_ia(canal_actual="Rescate_Estancado")
        else:
            st.success("Embudo limpio. No hay proyectos que superen su umbral de días sin movimiento.")

        if not sin_fecha.empty:
            with st.expander(f"{len(sin_fecha)} folios sin fecha válida (no se pueden evaluar)"):
                st.dataframe(sin_fecha[['ID_Proyecto', 'Cliente', 'Fase_Pipeline', 'Monto_USD', 'Monto_MXN']],
                             hide_index=True, use_container_width=True)
    else:
        st.info("Sube el CSV para auditar proyectos estancados.")

# ============================================================
# 3. LABORATORIO TÁCTICO IA
# ============================================================
with t_ai:
    st.subheader("Configuración de Paquete (Bundle) y Estrategia")
    if not df.empty:
        clientes = sorted(df['Cliente'].dropna().unique().tolist())
        c_sel_box = st.selectbox("1. Selecciona la Cuenta:", ["-- Selecciona --"] + clientes)
        if c_sel_box != "-- Selecciona --":
            c_sel = c_sel_box
            df_c = df[df['Cliente'] == c_sel]
            opciones = df_c.apply(
                lambda x: f"[{x['ID_Proyecto']}] {str(x['Descripcion'])} - ${x['Monto_USD']:,.0f} USD / ${x['Monto_MXN']:,.0f} MXN",
                axis=1).tolist()
            p_sel = st.multiselect("2. Agrupar Folios:", opciones)
            if p_sel:
                ids = [o.split("]")[0].replace("[", "") for o in p_sel]
                df_s = df[df['ID_Proyecto'].astype(str).isin(ids)]
                t_usd, t_mxn = float(df_s['Monto_USD'].sum()), float(df_s['Monto_MXN'].sum())
                eqs = " | ".join(df_s['Descripcion'].astype(str).tolist())
                num_proy = len(df_s)
                fase_bundle = max(df_s['Fase_Pipeline'], key=rango_fase)
                dias_bundle = df_s['Días_Sin_Mov'].min()
                dias_bundle = int(dias_bundle) if pd.notna(dias_bundle) else None
                st.markdown(
                    f"**Valor del Paquete:** <span style='color:green'>${t_usd:,.2f} USD</span> | "
                    f"<span style='color:purple'>${t_mxn:,.2f} MXN</span> | **Fase:** {esc(fase_bundle)}",
                    unsafe_allow_html=True)

                st.markdown("#### Configuración Táctica (Motor de Estrategia)")
                c1, c2 = st.columns(2)
                with c1:
                    obj_tactico = st.radio(
                        "Objetivo de la Estrategia:",
                        [
                            "Cierre / Negociación / Seguimiento Virtual",
                            "Apertura / Visita Presencial",
                            "Visita con Acompañamiento (Gerencia / Dirección)"
                        ]
                    )
                    canal = st.selectbox(
                        "Canal / Tipo de Acción:",
                        [
                            "Visita con Director / Acompañamiento",
                            "Cierre / Negociación de Propuesta",
                            "Correo Electrónico Ejecutivo",
                            "Guion de Llamada",
                            "Mensaje WhatsApp"
                        ]
                    )
                    interlocutor = st.selectbox(
                        "Interlocutor:",
                        [
                            "Comprador",
                            "Ingeniero / Planta",
                            "Gerente de Calidad / Operaciones",
                            "Director / Dueño"
                        ]
                    )
                with c2:
                    contexto = st.text_area(
                        "Notas Manuales (Contexto actual):",
                        placeholder="Ej. Visita a planta con gerencia para destrabar PO, o condiciones de crédito...",
                        height=180
                    )

                if st.button("Generar Estrategia", type="primary"):
                    if gemini_activo:
                        with st.spinner("Procesando estrategia con Gemini..."):
                            try:
                                datos_ia = ejecutar_ia(c_sel, interlocutor, num_proy, eqs, t_usd, t_mxn,
                                                       obj_tactico, canal, contexto,
                                                       fase=fase_bundle, dias=dias_bundle)
                                st.session_state.update(datos_ia)
                                st.session_state.update({
                                    'ai_cliente': c_sel,
                                    'ai_folio': ", ".join(ids),
                                    'ai_usd': t_usd,
                                    'ai_mxn': t_mxn,
                                    'ai_fase': fase_bundle,
                                    'ai_origen': "Laboratorio_IA"
                                })
                            except Exception as e:
                                st.error(f"Error API: {e}")
                    else:
                        st.error("Configura tu API Key de Gemini en Secrets.")

        mostrar_resultados_ia(canal_actual="Laboratorio_IA")
    else:
        st.info("Sube el archivo CSV del CRM para habilitar el Laboratorio Táctico.")

# ============================================================
# 4. REVOPS: ROI Y FORECAST
# ============================================================
with t_revops:
    t_roi, t_fc = st.tabs(["Calculadora ROI", "Forecast Automático"])

    with t_roi:
        st.subheader("Calculadora de ROI Metrológico")
        cr1, cr2 = st.columns(2)
        with cr1:
            inv = st.number_input("Inversión del Equipo (Ej. 60000 USD)", min_value=0.0, value=60000.0)
            c_hora = st.number_input("Costo Máquina CNC / Hora (USD)", min_value=0.0, value=50.0)
            horas_pieza = st.number_input("Horas de máquina perdidas por pieza rechazada", min_value=0.0, value=2.0, step=0.5)
            costo_mat = st.number_input("Costo de material por pieza rechazada (USD)", min_value=0.0, value=0.0)
            rechazo = st.number_input("Piezas rechazadas o retrabajadas por semana", min_value=0, value=10)
        with cr2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Calcular Retorno Financiero", type="primary"):
                costo_pieza = c_hora * horas_pieza + costo_mat
                filas = []
                for nombre, reduccion in ESCENARIOS_ROI.items():
                    ahorro = costo_pieza * rechazo * 52 * reduccion
                    meses = inv / (ahorro / 12) if ahorro > 0 else 999.0
                    filas.append({
                        "Escenario": nombre,
                        "Reducción de rechazos": f"{reduccion:.0%}",
                        "Ahorro anual (USD)": round(ahorro, 2),
                        "Retorno (meses)": round(meses, 1),
                    })
                st.session_state.roi_tabla = filas
                base = filas[1]
                st.session_state.roi_meses_num = float(base["Retorno (meses)"])
                st.session_state.roi_calc = (
                    f"Escenario base ({base['Reducción de rechazos']} de reducción de rechazos): "
                    f"ahorro anual estimado ${base['Ahorro anual (USD)']:,.2f} USD | "
                    f"retorno de inversión en {base['Retorno (meses)']:.1f} meses"
                )
            if st.session_state.get('roi_calc'):
                st.info(st.session_state.roi_calc)
        if st.session_state.get('roi_tabla'):
            st.dataframe(pd.DataFrame(st.session_state.roi_tabla), hide_index=True, use_container_width=True)
            st.caption("El escenario Base alimenta el argumento de la IA y el ROI guardado en el Forecast. "
                       "Los porcentajes de cada escenario se editan en ESCENARIOS_ROI al inicio del archivo.")

    with t_fc:
        st.subheader("Forecast Real (Pipeline Ponderado)")
        reps = run_query(
            "SELECT id, folio_proyecto, cliente, monto, probabilidad, semana, divisa, estatus, roi_calculado, fecha_prox FROM reportes"
        )
        if reps:
            df_fc = pd.DataFrame(reps, columns=["ID", "Folio", "Cliente", "Monto", "Prob(%)", "Semana", "Divisa",
                                                "Estatus", "ROI (Meses)", "Próx. acción"])
            df_fc["Próx. acción"] = pd.to_datetime(df_fc["Próx. acción"], errors="coerce").dt.date
            df_fc['Forecast_Real'] = df_fc['Monto'] * (df_fc['Prob(%)'].fillna(0) / 100.0)

            vivos = df_fc[df_fc['Estatus'] != "6. Perdido"]
            c_f1, c_f2 = st.columns(2)
            for divisa, col in zip(["USD", "MXN"], [c_f1, c_f2]):
                df_div = vivos[vivos['Divisa'] == divisa]
                col.metric(f"Forecast {divisa}", f"${df_div['Forecast_Real'].sum():,.2f}",
                           f"Pipeline Total: ${df_div['Monto'].sum():,.2f}", delta_color="off")

            # --- Acciones vencidas / próximas ---
            st.markdown("#### Acciones Vencidas y de los Próximos 7 Días")
            hoy_d = date.today()
            df_acc = df_fc[~df_fc['Estatus'].isin(["5. Cerrado Ganado", "6. Perdido"]) & df_fc['Próx. acción'].notna()]
            df_acc = df_acc[df_acc['Próx. acción'].apply(lambda d: d <= hoy_d + timedelta(days=7))]
            if not df_acc.empty:
                df_acc = df_acc.sort_values('Próx. acción').copy()
                df_acc['Situación'] = df_acc['Próx. acción'].apply(
                    lambda d: "Vencida" if d < hoy_d else ("Hoy" if d == hoy_d else "Próxima"))
                st.dataframe(df_acc[['Situación', 'Próx. acción', 'Cliente', 'Folio', 'Estatus']],
                             hide_index=True, use_container_width=True)
            else:
                st.success("Sin acciones vencidas ni próximas esta semana.")

            st.markdown("#### Edición Rápida de Forecast")
            st.caption("Modifica directamente la Probabilidad, Semana, Estatus o Próxima acción en la tabla y presiona 'Guardar Cambios'.")

            df_edit = st.data_editor(
                df_fc,
                disabled=["ID", "Folio", "Cliente", "Divisa", "Forecast_Real"],
                column_config={
                    "Prob(%)": st.column_config.NumberColumn("Prob(%)", min_value=0, max_value=100, step=5),
                    "Semana": st.column_config.SelectboxColumn("Semana", options=["W1", "W2", "W3", "W4"]),
                    "Estatus": st.column_config.SelectboxColumn("Estatus", options=FASES),
                    "Próx. acción": st.column_config.DateColumn("Próx. acción"),
                },
                hide_index=True,
                use_container_width=True,
                key="editor_forecast"
            )

            col_btn1, col_btn2 = st.columns([1, 2])
            with col_btn1:
                if st.button("Guardar Cambios en Forecast", type="primary", use_container_width=True):
                    for _, fila in df_edit.iterrows():
                        roi_f = fila["ROI (Meses)"]
                        roi_f = float(roi_f) if pd.notna(roi_f) else 0.0
                        fp = fila["Próx. acción"]
                        fp = fp.strftime("%Y-%m-%d") if pd.notna(fp) else None
                        run_query(
                            "UPDATE reportes SET monto=?, probabilidad=?, semana=?, estatus=?, roi_calculado=?, fecha_prox=? WHERE id=?",
                            (float(fila["Monto"]), int(fila["Prob(%)"]), str(fila["Semana"]), str(fila["Estatus"]),
                             roi_f, fp, int(fila["ID"])),
                            fetch=False
                        )
                    st.success("Forecast actualizado.")
                    st.rerun()
            with col_btn2:
                ids_borrar = st.multiselect(
                    "Seleccionar IDs para eliminar:", df_fc["ID"].tolist(),
                    format_func=lambda x: f"ID {x} - {df_fc[df_fc['ID'] == x]['Cliente'].values[0]} ({df_fc[df_fc['ID'] == x]['Folio'].values[0]})")
                confirmar = st.checkbox("Confirmo que quiero eliminar los registros seleccionados (no se puede deshacer)")
                if ids_borrar and confirmar and st.button("Eliminar Seleccionados", use_container_width=True):
                    for id_b in ids_borrar:
                        run_query("DELETE FROM reportes WHERE id=?", (int(id_b),), fetch=False)
                    st.warning("Registros eliminados.")
                    st.rerun()
        else:
            st.info("Sin registros en SQLite para calcular Forecast. Genera e inyecta una estrategia desde el Laboratorio Táctico IA.")
