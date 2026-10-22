# -*- coding: utf-8 -*-
"""
SAIV | Sistema Automatizado de Ingeniería de Ventas (Radar Comercial MESS)
Archivo único: app.py

Secrets requeridos (.streamlit/secrets.toml):
    mi_contrasena  = "tu_contraseña"
    GEMINI_API_KEY = "tu_api_key"
"""

import csv
import hmac
import io
import re
import sqlite3
import unicodedata
from datetime import datetime, date, time, timedelta
from urllib.parse import quote

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from docx import Document
    from docx.shared import Pt
except Exception:
    Document = None
    Pt = None

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------
MESS_BLUE = "#003a70"
MESS_DARK = "#2c3e50"
MESS_LIGHT = "#f8fafc"
ALERT_RED = "#c0392b"
ACCENT = "#e67e22"

DB_PATH = "mess_radar.db"
MODEL_NAME = "gemini-pro"

FASES = {
    0: "0. Perdido/Cancelado",
    1: "1. Propuesta",
    2: "2. Cotización",
    3: "3. Negociación",
    4: "4. Esperando PO",
    5: "5. Cerrado Ganado",
}
PROB_FASE = {0: 0.0, 1: 0.10, 2: 0.25, 3: 0.50, 4: 0.80, 5: 1.0}

PILAR_ALTA = "1. Alta Gama"
PILAR_CAL = "2. Calibraciones"
PILAR_GEN = "3. Productos Generales"

KW_CALIBRACION = [
    "CALIBR", "CERTIFICADO", "PATRON", "VERIFICACION", "TRAZABILIDAD",
    "MANTENIMIENTO", "SERVICIO", "EMA", "ACREDIT",
]
KW_ALTA_GAMA = [
    "CMM", "COORDENADA", "ESCANER", "SCANNER", "3D", "LASER", "TRACKER",
    "BRAZO", "OPTIC", "MICROSCOP", "ALTA GAMA", "PROYECTOR", "METROTOM",
    "TOMOGRAF", "VIDEO", "MEDICION POR",
]

SEMANAS = ["W1", "W2", "W3", "W4"]
ESTATUS_AGENDA = ["Programada", "Realizada", "Reprogramada", "Cancelada"]
MONEDAS = ["USD", "MXN"]

OBJETIVOS = [
    "Agendar visita técnica",
    "Enviar y dar seguimiento a cotización",
    "Reactivar proyecto estancado",
    "Negociar y obtener PO",
    "Cross-selling de Calibraciones o Alta Gama",
    "Primer contacto (Showroom)",
]
CANALES = ["WhatsApp", "Correo", "Llamada", "Visita"]
GIROS = [
    "Aeronáutico", "Automotriz", "Metalmecánico", "Manufactura general",
    "Médico", "Energía", "Otro",
]

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SAIV | Radar Comercial MESS",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {
    font-family: 'Montserrat', sans-serif !important;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.stApp { background-color: #f8fafc; }
h1, h2, h3, h4 { color: #003a70; font-weight: 700; }

section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }

.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 6px solid #003a70;
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 2px 6px rgba(0, 58, 112, 0.08);
    margin-bottom: 10px;
}
.kpi-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #2c3e50; font-weight: 600; }
.kpi-value { font-size: 1.7rem; font-weight: 700; color: #003a70; line-height: 1.2; }
.kpi-sub { font-size: 0.75rem; color: #64748b; }

.alert-card {
    background: #fff5f5;
    border: 1px solid #f5c6cb;
    border-left: 6px solid #c0392b;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 6px;
    box-shadow: 0 2px 6px rgba(192, 57, 43, 0.08);
}
.alert-title { font-weight: 700; color: #c0392b; }
.alert-body { font-size: 0.85rem; color: #2c3e50; }

.stButton > button {
    background-color: #003a70; color: #ffffff; border: none; border-radius: 6px; font-weight: 600;
}
.stButton > button:hover { background-color: #002a52; color: #ffffff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SEGURIDAD
# ---------------------------------------------------------------------------
def check_password():
    """Bloquea la app hasta que se capture la contraseña de st.secrets."""
    if st.session_state.get("auth_ok"):
        return True
    st.sidebar.markdown("### Acceso")
    try:
        secret = str(st.secrets["mi_contrasena"])
    except Exception:
        st.sidebar.error("No se encontró 'mi_contrasena' en st.secrets.")
        return False
    pwd = st.sidebar.text_input("Contraseña", type="password", key="pwd_input")
    if pwd:
        if hmac.compare_digest(pwd.encode("utf-8"), secret.encode("utf-8")):
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.sidebar.error("Contraseña incorrecta.")
    return False


if not check_password():
    st.title("SAIV | Radar Comercial MESS")
    st.info("Ingresa la contraseña en el panel lateral para continuar.")
    st.stop()


# ---------------------------------------------------------------------------
# UTILIDADES GENERALES
# ---------------------------------------------------------------------------
def norm(text):
    """Mayúsculas sin acentos ni espacios extremos."""
    s = "" if text is None else str(text)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper().strip()


def fmt_money(x, cur="USD"):
    try:
        return "$" + format(float(x), ",.0f") + " " + cur
    except Exception:
        return "$0 " + cur


def week_label(d=None):
    d = d or date.today()
    return "W" + str(min(4, (d.day - 1) // 7 + 1))


def show_chart(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def kpi_card(label, value, sub=""):
    html = (
        '<div class="kpi-card">'
        '<div class="kpi-label">' + label + "</div>"
        '<div class="kpi-value">' + value + "</div>"
        '<div class="kpi-sub">' + sub + "</div>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def parse_date_safe(s, default=None):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except Exception:
        return default or date.today()


def parse_time_safe(s, default=None):
    try:
        return datetime.strptime(str(s)[:5], "%H:%M").time()
    except Exception:
        return default or time(10, 0)


# ---------------------------------------------------------------------------
# MOTOR DE EXTRACCIÓN (PANDAS)
# ---------------------------------------------------------------------------
def decode_bytes(raw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def detect_delimiter(text):
    sample = text[:5000]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except Exception:
        return ","


def find_col(columns, keys, exclude=()):
    for key in keys:
        for c in columns:
            n = norm(c)
            if key in n and not any(x in n for x in exclude):
                return c
    return None


def parse_amount(val):
    """Extrae un número de texto tipo '$ 12,500.00 USD'."""
    try:
        if val is None:
            return 0.0
        s = str(val)
        if s.strip() == "" or s.strip().lower() == "nan":
            return 0.0
        s = re.sub(r"(?i)usd|mxn|us\$|\$", "", s)
        s = s.replace(",", "").replace(" ", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group()) if m else 0.0
    except Exception:
        return 0.0


def classify_pillar(text):
    t = norm(text)
    if any(k in t for k in KW_CALIBRACION):
        return PILAR_CAL
    if any(k in t for k in KW_ALTA_GAMA):
        return PILAR_ALTA
    return PILAR_GEN


def classify_phase(text):
    t = norm(text)
    if t == "":
        return 1
    if re.search(r"PERDID|CANCEL|LOST|DECLIN", t):
        return 0
    if re.search(r"GANAD|CERRAD|WON|FACTURAD", t):
        return 5
    if re.search(r"\bPO\b|ORDEN DE COMPRA|ESPERANDO|\bOC\b", t):
        return 4
    if re.search(r"NEGOCI|AUTORIZ|REVISION", t):
        return 3
    if re.search(r"COTIZ|QUOTE", t):
        return 2
    return 1


@st.cache_data(show_spinner=False)
def load_crm(raw_bytes):
    """Lee el CSV de SCOTT y devuelve (DataFrame agrupado por proyecto, avisos)."""
    avisos = []
    text = decode_bytes(raw_bytes)
    delim = detect_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delim))

    header_idx = None
    for i, r in enumerate(rows):
        joined = " ".join(norm(c) for c in r)
        if "PROYECTO" in joined and "CLIENTE" in joined:
            header_idx = i
            break
    if header_idx is None:
        return None, ["No se encontró una fila con los encabezados PROYECTO y CLIENTE."]

    body = rows[header_idx + 1:]
    width = max([len(rows[header_idx])] + [len(r) for r in body]) if body else len(rows[header_idx])
    header = list(rows[header_idx]) + [""] * (width - len(rows[header_idx]))
    names, seen = [], {}
    for i, h in enumerate(header):
        h = str(h).strip() or "COL_" + str(i)
        if h in seen:
            seen[h] += 1
            h = h + "_" + str(seen[h])
        else:
            seen[h] = 0
        names.append(h)

    data = [list(r) + [""] * (width - len(r)) for r in body]
    df = pd.DataFrame(data, columns=names)
    df = df.apply(lambda col: col.astype(str).str.strip())
    df = df[~(df == "").all(axis=1)].reset_index(drop=True)
    if df.empty:
        return None, ["El archivo no contiene filas con datos después de los encabezados."]

    cols = list(df.columns)
    c_proy = find_col(cols, ["PROYECTO", "FOLIO"])
    c_cli = find_col(cols, ["CLIENTE"])
    c_desc = find_col(cols, ["DESCRIP", "CONCEPTO", "PRODUCTO", "EQUIPO"])
    c_area = find_col(cols, ["AREA", "LINEA", "FAMILIA", "DIVISION"])
    c_etapa = find_col(cols, ["ETAPA", "FASE", "ESTATUS", "STATUS"])
    c_mon = find_col(cols, ["MONEDA", "DIVISA"])
    c_fecha = find_col(cols, ["ULTIMA", "ACTUALIZ", "MODIF", "SEGUIM", "FECHA"])
    monto_cols = [
        c for c in cols
        if any(k in norm(c) for k in ["MONTO", "IMPORTE", "TOTAL", "VALOR", "PRECIO"])
        and c not in (c_mon,)
    ]

    if c_proy is None or c_cli is None:
        return None, ["No se pudieron identificar las columnas PROYECTO y CLIENTE."]
    if not monto_cols:
        avisos.append("No se detectó columna de monto; los importes quedarán en cero.")
    if c_etapa is None:
        avisos.append("No se detectó columna de etapa; todo se clasifica como 1. Propuesta.")

    work = pd.DataFrame()
    work["ID_Proyecto"] = df[c_proy].replace("", np.nan)
    work["ID_Proyecto"] = work["ID_Proyecto"].fillna(
        pd.Series(["S/N-" + str(i) for i in range(len(df))])
    )
    work["Cliente"] = df[c_cli].replace("", "Sin cliente")
    work["Descripcion"] = df[c_desc] if c_desc else ""
    work["Area"] = df[c_area] if c_area else ""
    work["Etapa_Orig"] = df[c_etapa] if c_etapa else ""

    usd_list, mxn_list = [], []
    for idx in df.index:
        row_cur = norm(df.at[idx, c_mon]) if c_mon else ""
        usd_tot, mxn_tot = 0.0, 0.0
        for mc in monto_cols:
            cell = df.at[idx, mc]
            amt = parse_amount(cell)
            if amt == 0:
                continue
            is_usd = ("USD" in norm(cell)) or ("USD" in norm(mc)) or ("USD" in row_cur)
            if is_usd:
                usd_tot += amt
            else:
                mxn_tot += amt
        usd_list.append(usd_tot)
        mxn_list.append(mxn_tot)
    work["Monto_USD"] = usd_list
    work["Monto_MXN"] = mxn_list

    if c_fecha:
        work["Fecha"] = pd.to_datetime(df[c_fecha], dayfirst=True, errors="coerce")
    else:
        work["Fecha"] = pd.NaT
        avisos.append("No se detectó columna de fecha; los días de inactividad se calculan en 0.")

    work["Fase_Num"] = work["Etapa_Orig"].apply(classify_phase)

    def uniq_join(s, sep):
        vals = [str(x).strip() for x in s if str(x).strip() not in ("", "nan")]
        return sep.join(dict.fromkeys(vals))

    agg = work.groupby("ID_Proyecto", sort=False).agg(
        Cliente=("Cliente", "first"),
        Descripcion=("Descripcion", lambda s: uniq_join(s, " | ")),
        Area=("Area", lambda s: uniq_join(s, " / ")),
        Etapa_Orig=("Etapa_Orig", "first"),
        Fase_Num=("Fase_Num", "max"),
        Monto_USD=("Monto_USD", "sum"),
        Monto_MXN=("Monto_MXN", "sum"),
        Fecha=("Fecha", "max"),
    ).reset_index()

    agg["Pilar"] = (agg["Area"].fillna("") + " " + agg["Descripcion"].fillna("")).apply(classify_pillar)
    agg["Fase"] = agg["Fase_Num"].map(FASES)
    hoy = pd.Timestamp.today().normalize()
    agg["Dias_Inactivo"] = (hoy - agg["Fecha"]).dt.days.fillna(0).astype(int)
    agg["Prob"] = agg["Fase_Num"].map(PROB_FASE).fillna(0.0)
    return agg, avisos


# ---------------------------------------------------------------------------
# BASE DE DATOS LOCAL (SQLITE)
# ---------------------------------------------------------------------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS agenda ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, hora TEXT, "
            "cliente TEXT, estatus TEXT)"
        )
        con.execute(
            "CREATE TABLE IF NOT EXISTS bitacora ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, cliente TEXT, "
            "resumen TEXT, siguiente_paso TEXT, monto REAL, moneda TEXT, "
            "probabilidad INTEGER, semana TEXT)"
        )
        con.commit()
    finally:
        con.close()


def db_df(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def db_exec(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


init_db()


# ---------------------------------------------------------------------------
# INTELIGENCIA ARTIFICIAL (GEMINI)
# ---------------------------------------------------------------------------
def call_gemini(prompt):
    """Devuelve (texto, error)."""
    if genai is None:
        return None, "Falta instalar la librería google-generativeai."
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None, "Falta GEMINI_API_KEY en st.secrets."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content(prompt)
        return resp.text, None
    except Exception as e:
        return None, "Error al consultar Gemini: " + str(e)


def parse_tags(text):
    out = {}
    for tag in ["ANALYSIS", "MESSAGE", "OBJECTIONS", "MARKETING", "LOG"]:
        pattern = "<" + tag + ">(.*?)(?=</" + tag + ">|<[A-Z]+>|$)"
        m = re.search(pattern, text or "", re.S | re.I)
        out[tag] = m.group(1).strip() if m else ""
    return out


def build_prompt(ctx):
    lines = [
        "Actúa como Javier Camacho, Key Account Manager (KAM) B2B de MESS Servicios Metrológicos en Querétaro, México.",
        "Fusiona de forma natural y humana las metodologías MEDDPICC, SPIN Selling y Sandler.",
        "Estilo: consultivo, directo, profesional, sin exageraciones técnicas ni lenguaje de marketing inflado. Frases cortas y claras.",
        "",
        "CONTEXTO DE LA OPORTUNIDAD:",
        "- Cliente: " + ctx["cliente"],
        "- Folios o proyectos agrupados (bundle): " + ctx["folios"],
        "- Descripción de lo cotizado: " + ctx["descripcion"],
        "- Monto: " + ctx["monto_txt"],
        "- Fase actual del pipeline: " + ctx["fase"],
        "- Objetivo de la acción: " + ctx["objetivo"],
        "- Canal: " + ctx["canal"],
        "- Interlocutor: " + (ctx["interlocutor"] or "No especificado"),
        "- Giro industrial: " + ctx["giro"],
        "- Contexto adicional del KAM: " + (ctx["contexto"] or "Ninguno"),
        "",
        "INSTRUCCIONES DE FORMATO:",
        "Responde ÚNICAMENTE con estas cinco etiquetas XML, en este orden, sin texto fuera de ellas y sin bloques de código:",
        "<ANALYSIS> Diagnóstico breve con MEDDPICC: qué sabemos, qué falta validar (métricas, comprador económico, criterios de decisión, proceso, dolor, champion, competencia) y la mejor jugada. </ANALYSIS>",
        "<MESSAGE> Mensaje listo para enviar por el canal indicado, con tono humano, preguntas tipo SPIN y un cierre claro. Adapta la longitud al canal. </MESSAGE>",
        "<OBJECTIONS> Las 3 objeciones más probables y cómo responderlas con enfoque Sandler (sin presionar). </OBJECTIONS>",
        "<MARKETING> Ángulo de valor y material de apoyo sugerido (casos, certificados, fichas) para este giro. </MARKETING>",
        "<LOG> Resumen de 2 a 4 líneas para la bitácora comercial: qué se hará, con quién y siguiente paso. </LOG>",
    ]
    return "\n".join(lines)


def build_rescue_prompt(row):
    lines = [
        "Actúa como Javier Camacho, Key Account Manager B2B de MESS Servicios Metrológicos.",
        "Un proyecto lleva " + str(int(row["Dias_Inactivo"])) + " días sin movimiento en fase inicial.",
        "- Cliente: " + str(row["Cliente"]),
        "- Proyecto: " + str(row["ID_Proyecto"]),
        "- Descripción: " + str(row["Descripcion"])[:300],
        "- Monto aproximado: " + fmt_money(row["Monto_USD"], "USD") + " y " + fmt_money(row["Monto_MXN"], "MXN"),
        "",
        "Aplica la técnica de cierre negativo de Sandler: dale permiso al cliente de decir que no, sin presionar, para provocar una respuesta honesta.",
        "Entrega: 1) un mensaje corto de WhatsApp listo para enviar (máximo 60 palabras, tono humano y directo) y 2) una línea explicando la lógica del mensaje.",
        "Usa las etiquetas <MESSAGE> y <ANALYSIS> respectivamente.",
    ]
    return "\n".join(lines)


def whatsapp_link(message, phone=""):
    base = "https://web.whatsapp.com/send?"
    phone = re.sub(r"\D", "", phone or "")
    if phone:
        base += "phone=" + phone + "&"
    return base + "text=" + quote(message or "")


def gcal_link(title, details, start_dt, minutes=60):
    end_dt = start_dt + timedelta(minutes=minutes)
    fmt = "%Y%m%dT%H%M%S"
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        + "&text=" + quote(title)
        + "&details=" + quote((details or "")[:1500])
        + "&dates=" + start_dt.strftime(fmt) + "/" + end_dt.strftime(fmt)
    )


def build_docx(ctx, tags):
    doc = Document()
    try:
        doc.styles["Normal"].font.name = "Montserrat"
        doc.styles["Normal"].font.size = Pt(10)
    except Exception:
        pass
    doc.add_heading("Ficha Táctica | MESS Servicios Metrológicos", level=1)
    doc.add_paragraph("Cliente: " + ctx["cliente"])
    doc.add_paragraph("Folios: " + ctx["folios"])
    doc.add_paragraph("Monto: " + ctx["monto_txt"])
    doc.add_paragraph("Objetivo: " + ctx["objetivo"] + " | Canal: " + ctx["canal"])
    doc.add_paragraph("Interlocutor: " + (ctx["interlocutor"] or "No especificado") + " | Giro: " + ctx["giro"])
    secciones = [
        ("Análisis MEDDPICC", "ANALYSIS"),
        ("Mensaje", "MESSAGE"),
        ("Manejo de objeciones", "OBJECTIONS"),
        ("Marketing y material de apoyo", "MARKETING"),
        ("Registro para bitácora", "LOG"),
    ]
    for titulo, tag in secciones:
        doc.add_heading(titulo, level=2)
        doc.add_paragraph(tags.get(tag, "") or "Sin contenido.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# TAB 1: DASHBOARDS CRM
# ---------------------------------------------------------------------------
def render_dashboard(crm, meta, tc):
    st.subheader("Dashboards CRM")
    if crm is None:
        st.info("Carga el CSV del CRM (SCOTT) en el panel lateral para ver los indicadores.")
        return

    vivo = crm[crm["Fase_Num"] > 0]
    activo = vivo[vivo["Fase_Num"].between(1, 4)]
    ganado = vivo[vivo["Fase_Num"] == 5]

    probable = float((activo["Total_USD_Eq"] * activo["Prob"]).sum())
    cerrado = float(ganado["Total_USD_Eq"].sum())
    gap = meta - (probable + cerrado)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Meta mensual", fmt_money(meta), "Objetivo de venta")
    with c2:
        kpi_card("Pipeline probable activo", fmt_money(probable), "Monto x probabilidad por fase")
    with c3:
        kpi_card("Cerrado ganado", fmt_money(cerrado), "Fase 5")
    with c4:
        kpi_card("Brecha (GAP)", fmt_money(gap), "Meta menos probable y ganado")

    st.caption("Importes en MXN convertidos a USD con tipo de cambio " + str(tc) + ". Probabilidades por fase: 10%, 25%, 50% y 80%.")

    st.markdown("#### Pareto 80/20 por cliente")
    par = vivo.groupby("Cliente")["Total_USD_Eq"].sum().sort_values(ascending=False)
    if par.sum() > 0:
        pdf = par.reset_index()
        pdf.columns = ["Cliente", "Monto"]
        pdf["Acumulado"] = pdf["Monto"].cumsum() / pdf["Monto"].sum() * 100
        pdf = pdf.head(15)
        base = alt.Chart(pdf).encode(x=alt.X("Cliente:N", sort=None, title=None))
        barras = base.mark_bar(color=MESS_BLUE).encode(
            y=alt.Y("Monto:Q", title="Monto USD equivalente"),
            tooltip=["Cliente", alt.Tooltip("Monto:Q", format=",.0f")],
        )
        linea = base.mark_line(color=ACCENT, point=True).encode(
            y=alt.Y("Acumulado:Q", scale=alt.Scale(domain=[0, 100]), title="% acumulado"),
            tooltip=["Cliente", alt.Tooltip("Acumulado:Q", format=".1f")],
        )
        regla = alt.Chart(pd.DataFrame({"y": [80]})).mark_rule(
            color=ALERT_RED, strokeDash=[5, 5]
        ).encode(y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 100])))
        chart = alt.layer(barras, linea + regla).resolve_scale(y="independent").properties(height=340)
        show_chart(chart)
    else:
        st.info("No hay montos para construir el Pareto.")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Forecast por área")
        fa = activo.assign(Forecast=activo["Total_USD_Eq"] * activo["Prob"]).groupby("Pilar")["Forecast"].sum().reset_index()
        if not fa.empty and fa["Forecast"].sum() > 0:
            ch = alt.Chart(fa).mark_bar(color=MESS_BLUE).encode(
                y=alt.Y("Pilar:N", sort="-x", title=None),
                x=alt.X("Forecast:Q", title="Forecast USD"),
                tooltip=["Pilar", alt.Tooltip("Forecast:Q", format=",.0f")],
            ).properties(height=220)
            show_chart(ch)
        else:
            st.info("Sin pipeline activo.")
    with g2:
        st.markdown("#### Salud del embudo")
        fe = vivo.groupby("Fase")["Total_USD_Eq"].sum().reset_index()
        if not fe.empty:
            ch = alt.Chart(fe).mark_bar(color=MESS_DARK).encode(
                y=alt.Y("Fase:N", sort="ascending", title=None),
                x=alt.X("Total_USD_Eq:Q", title="Monto USD equivalente"),
                tooltip=["Fase", alt.Tooltip("Total_USD_Eq:Q", format=",.0f")],
            ).properties(height=220)
            show_chart(ch)

    st.markdown("#### Cross-Selling: consumen Calibraciones y tienen $0 en Alta Gama")
    piv = vivo.pivot_table(index="Cliente", columns="Pilar", values="Total_USD_Eq", aggfunc="sum", fill_value=0)
    for col in [PILAR_ALTA, PILAR_CAL, PILAR_GEN]:
        if col not in piv.columns:
            piv[col] = 0.0
    oport = piv[(piv[PILAR_CAL] > 0) & (piv[PILAR_ALTA] == 0)].sort_values(PILAR_CAL, ascending=False)
    if oport.empty:
        st.success("No hay clientes con ese patrón.")
    else:
        st.dataframe(oport[[PILAR_CAL, PILAR_ALTA]].round(0), width="stretch")


# ---------------------------------------------------------------------------
# TAB 2: PROYECTOS ESTANCADOS
# ---------------------------------------------------------------------------
def render_stalled(crm):
    st.subheader("Proyectos estancados")
    if crm is None:
        st.info("Carga el CSV del CRM para detectar proyectos estancados.")
        return
    est = crm[(crm["Fase_Num"].between(1, 2)) & (crm["Dias_Inactivo"] > 15)]
    est = est.sort_values("Dias_Inactivo", ascending=False)
    if est.empty:
        st.success("No hay proyectos en fases iniciales con más de 15 días de inactividad.")
        return
    st.caption(str(len(est)) + " proyecto(s) en fase inicial con más de 15 días sin movimiento.")

    for _, row in est.iterrows():
        pid = str(row["ID_Proyecto"])
        html = (
            '<div class="alert-card">'
            '<div class="alert-title">' + str(row["Cliente"]) + " | " + pid + "</div>"
            '<div class="alert-body">' + str(row["Fase"]) + " | "
            + str(int(row["Dias_Inactivo"])) + " días inactivo | "
            + fmt_money(row["Monto_USD"], "USD") + " / " + fmt_money(row["Monto_MXN"], "MXN") + "<br>"
            + str(row["Descripcion"])[:160] + "</div></div>"
        )
        st.markdown(html, unsafe_allow_html=True)
        key_res = "rescate_" + pid
        if st.button("Generar Rescate", key="btn_" + key_res):
            with st.spinner("Generando mensaje de rescate..."):
                txt, err = call_gemini(build_rescue_prompt(row))
            st.session_state[key_res] = ("ERR:" + err) if err else txt
        if key_res in st.session_state:
            res = st.session_state[key_res]
            if str(res).startswith("ERR:"):
                st.error(res[4:])
            else:
                tags = parse_tags(res)
                msg = tags["MESSAGE"] or res
                st.markdown("**Mensaje sugerido (cierre negativo de Sandler)**")
                st.write(msg)
                if tags["ANALYSIS"]:
                    st.caption(tags["ANALYSIS"])
                st.link_button("Abrir en WhatsApp Web", whatsapp_link(msg))
        st.divider()


# ---------------------------------------------------------------------------
# TAB 3: LABORATORIO TÁCTICO IA
# ---------------------------------------------------------------------------
def render_lab(crm):
    st.subheader("Laboratorio Táctico IA (KAM)")
    origen = st.radio(
        "Origen de datos",
        ["CSV del CRM (SCOTT)", "Prospecto Manual / Showroom"],
        horizontal=True,
    )

    cliente = ""
    folios_txt = ""
    desc_txt = ""
    m_usd, m_mxn = 0.0, 0.0
    fase_txt = "Sin fase (prospecto nuevo)"
    prob_ini = 25
    ready = False

    if origen.startswith("CSV"):
        if crm is None:
            st.info("Carga el CSV del CRM en el panel lateral o usa Prospecto Manual.")
        else:
            clientes = sorted(crm["Cliente"].dropna().unique().tolist())
            cliente = st.selectbox("Cliente", clientes)
            sub = crm[crm["Cliente"] == cliente]
            etiquetas = {}
            for _, r in sub.iterrows():
                etiquetas[r["ID_Proyecto"]] = (
                    str(r["ID_Proyecto"]) + " | " + str(r["Descripcion"])[:60]
                    + " | " + fmt_money(r["Monto_USD"], "USD") + " / " + fmt_money(r["Monto_MXN"], "MXN")
                )
            opciones = list(etiquetas.keys())
            sel = st.multiselect(
                "Folios a cotizar en paquete (Bundle)",
                opciones,
                default=opciones[:1],
                format_func=lambda x: etiquetas.get(x, str(x)),
            )
            elegidos = sub[sub["ID_Proyecto"].isin(sel)]
            if not elegidos.empty:
                ready = True
                folios_txt = ", ".join(str(x) for x in elegidos["ID_Proyecto"])
                desc_txt = " | ".join(elegidos["Descripcion"].astype(str))[:800]
                m_usd = float(elegidos["Monto_USD"].sum())
                m_mxn = float(elegidos["Monto_MXN"].sum())
                fmax = int(elegidos["Fase_Num"].max())
                fase_txt = FASES.get(fmax, "N/A")
                prob_ini = int(PROB_FASE.get(fmax, 0.25) * 100)
                st.caption(
                    "Paquete: " + fmt_money(m_usd, "USD") + " y " + fmt_money(m_mxn, "MXN")
                    + " | " + fase_txt
                )
    else:
        m1, m2 = st.columns(2)
        with m1:
            cliente = st.text_input("Empresa o prospecto")
            desc_txt = st.text_area("Equipos o servicios de interés", height=90)
        with m2:
            mon = st.selectbox("Moneda estimada", MONEDAS)
            monto = st.number_input("Monto estimado", min_value=0.0, step=1000.0)
        if mon == "USD":
            m_usd = float(monto)
        else:
            m_mxn = float(monto)
        folios_txt = "Prospecto manual"
        ready = bool(cliente.strip())

    st.markdown("##### Controles de táctica")
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        objetivo = st.selectbox("Objetivo", OBJETIVOS)
    with t2:
        canal = st.selectbox("Canal", CANALES)
    with t3:
        interlocutor = st.text_input("Interlocutor", placeholder="Ej. Gerente de Calidad")
    with t4:
        giro = st.selectbox("Giro industrial", GIROS)
    contexto = st.text_area("Contexto manual", height=90, placeholder="Información adicional que conozcas del cliente.")

    if st.button("Generar estrategia", disabled=not ready):
        monto_txt = fmt_money(m_usd, "USD") + " y " + fmt_money(m_mxn, "MXN")
        ctx = {
            "cliente": cliente, "folios": folios_txt, "descripcion": desc_txt or "No especificada",
            "monto_txt": monto_txt, "fase": fase_txt, "objetivo": objetivo, "canal": canal,
            "interlocutor": interlocutor, "giro": giro, "contexto": contexto,
            "m_usd": m_usd, "m_mxn": m_mxn, "prob": prob_ini,
        }
        with st.spinner("Consultando a Gemini..."):
            txt, err = call_gemini(build_prompt(ctx))
        if err:
            st.error(err)
        else:
            st.session_state["ia_ctx"] = ctx
            st.session_state["ia_raw"] = txt
            st.session_state["ia_tags"] = parse_tags(txt)
            st.session_state["ia_id"] = st.session_state.get("ia_id", 0) + 1

    if "ia_tags" not in st.session_state:
        return

    ctx = st.session_state["ia_ctx"]
    tags = st.session_state["ia_tags"]
    rid = st.session_state["ia_id"]
    if not any(tags.values()):
        st.warning("La IA no devolvió las etiquetas esperadas. Se muestra la respuesta completa.")
        st.write(st.session_state["ia_raw"])
        return

    st.markdown("---")
    st.markdown("#### Resultado para " + ctx["cliente"])
    pa, pm, po, pk, pl = st.tabs(["Análisis", "Mensaje", "Objeciones", "Marketing", "Log"])
    with pa:
        st.write(tags["ANALYSIS"])
    with pm:
        mensaje = st.text_area("Mensaje (editable)", value=tags["MESSAGE"], height=200, key="msg_" + str(rid))
    with po:
        st.write(tags["OBJECTIONS"])
    with pk:
        st.write(tags["MARKETING"])
    with pl:
        log_txt = st.text_area("Log para bitácora (editable)", value=tags["LOG"], height=120, key="log_" + str(rid))

    st.markdown("##### Ejecución rápida")
    a1, a2 = st.columns(2)
    with a1:
        phone = st.text_input("Teléfono WhatsApp (opcional, con lada, ej. 524421234567)", key="ph_" + str(rid))
        st.link_button("Abrir WhatsApp Web con el mensaje", whatsapp_link(mensaje, phone))
    with a2:
        d1, d2 = st.columns(2)
        with d1:
            f_cita = st.date_input("Fecha de cita", value=date.today() + timedelta(days=1), key="fc_" + str(rid))
        with d2:
            h_cita = st.time_input("Hora", value=time(10, 0), key="hc_" + str(rid))
        inicio = datetime.combine(f_cita, h_cita)
        st.link_button(
            "Crear evento en Google Calendar",
            gcal_link("Visita MESS | " + ctx["cliente"], ctx["objetivo"] + "\n\n" + (log_txt or ""), inicio),
        )

    b1, b2, b3 = st.columns(3)
    with b1:
        if Document is None:
            st.warning("Instala python-docx para descargar la ficha .docx.")
        else:
            try:
                data = build_docx(ctx, {**tags, "MESSAGE": mensaje, "LOG": log_txt})
                st.download_button(
                    "Descargar ficha .docx",
                    data=data,
                    file_name="Ficha_" + re.sub(r"\W+", "_", ctx["cliente"]) + ".docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            except Exception as e:
                st.error("No se pudo generar el .docx: " + str(e))
    moneda_log = "USD" if ctx["m_usd"] > 0 else "MXN"
    monto_log = ctx["m_usd"] if ctx["m_usd"] > 0 else ctx["m_mxn"]
    with b2:
        if st.button("Inyectar LOG a RevOps (guardar)", key="inj_" + str(rid)):
            try:
                db_exec(
                    "INSERT INTO bitacora (fecha, cliente, resumen, siguiente_paso, monto, moneda, probabilidad, semana) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (date.today().isoformat(), ctx["cliente"], log_txt, ctx["objetivo"],
                     float(monto_log), moneda_log, int(ctx["prob"]), week_label()),
                )
                st.success("LOG guardado en la Bitácora.")
            except Exception as e:
                st.error("No se pudo guardar: " + str(e))
    with b3:
        if st.button("Precargar en formulario de Bitácora", key="pre_" + str(rid)):
            st.session_state["bitacora_prefill"] = {
                "cliente": ctx["cliente"], "resumen": log_txt, "siguiente_paso": ctx["objetivo"],
                "monto": float(monto_log), "moneda": moneda_log,
                "probabilidad": int(ctx["prob"]), "semana": week_label(),
            }
            st.success("Datos listos. Abre Gestión Comercial > Bitácora.")


# ---------------------------------------------------------------------------
# TAB 4: GESTIÓN COMERCIAL (REVOPS)
# ---------------------------------------------------------------------------
def render_agenda():
    st.markdown("##### Nueva visita")
    with st.form("agenda_new", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f = st.date_input("Fecha", value=date.today())
        with c2:
            h = st.time_input("Hora", value=time(10, 0))
        with c3:
            cli = st.text_input("Cliente")
        with c4:
            est = st.selectbox("Estatus", ESTATUS_AGENDA)
        if st.form_submit_button("Agregar"):
            if cli.strip():
                db_exec("INSERT INTO agenda (fecha, hora, cliente, estatus) VALUES (?,?,?,?)",
                        (f.isoformat(), h.strftime("%H:%M"), cli.strip(), est))
                st.success("Visita agregada.")
                st.rerun()
            else:
                st.warning("Captura el cliente.")

    df = db_df("SELECT * FROM agenda ORDER BY fecha, hora")
    st.markdown("##### Agenda")
    if df.empty:
        st.info("Aún no hay visitas registradas.")
        return
    st.dataframe(df, width="stretch", hide_index=True)

    st.markdown("##### Editar o eliminar")
    ids = df["id"].tolist()
    sel = st.selectbox(
        "Visita", ids,
        format_func=lambda i: str(i) + " | " + str(df.loc[df["id"] == i, "cliente"].iloc[0])
        + " | " + str(df.loc[df["id"] == i, "fecha"].iloc[0]),
        key="ag_sel",
    )
    r = df[df["id"] == sel].iloc[0]
    with st.form("agenda_edit_" + str(sel)):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f = st.date_input("Fecha", value=parse_date_safe(r["fecha"]), key="ag_f_" + str(sel))
        with c2:
            h = st.time_input("Hora", value=parse_time_safe(r["hora"]), key="ag_h_" + str(sel))
        with c3:
            cli = st.text_input("Cliente", value=str(r["cliente"]), key="ag_c_" + str(sel))
        with c4:
            idx = ESTATUS_AGENDA.index(r["estatus"]) if r["estatus"] in ESTATUS_AGENDA else 0
            est = st.selectbox("Estatus", ESTATUS_AGENDA, index=idx, key="ag_e_" + str(sel))
        u, d = st.columns(2)
        with u:
            do_upd = st.form_submit_button("Actualizar")
        with d:
            do_del = st.form_submit_button("Eliminar")
        if do_upd:
            db_exec("UPDATE agenda SET fecha=?, hora=?, cliente=?, estatus=? WHERE id=?",
                    (f.isoformat(), h.strftime("%H:%M"), cli.strip(), est, int(sel)))
            st.rerun()
        if do_del:
            db_exec("DELETE FROM agenda WHERE id=?", (int(sel),))
            st.rerun()


def render_bitacora():
    pre = st.session_state.get("bitacora_prefill")
    if pre:
        st.info("Formulario precargado desde el Laboratorio Táctico IA.")
        if st.button("Descartar precarga"):
            st.session_state.pop("bitacora_prefill", None)
            st.rerun()
    pre = pre or {}

    st.markdown("##### Nuevo reporte post-visita")
    with st.form("bit_new"):
        c1, c2 = st.columns(2)
        with c1:
            f = st.date_input("Fecha", value=date.today())
            cli = st.text_input("Cliente", value=pre.get("cliente", ""))
            sig = st.text_input("Siguiente paso", value=pre.get("siguiente_paso", ""))
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1000.0, value=float(pre.get("monto", 0.0)))
            mon_def = pre.get("moneda", "USD")
            mon = st.selectbox("Moneda", MONEDAS, index=MONEDAS.index(mon_def) if mon_def in MONEDAS else 0)
            prob = st.slider("Probabilidad (%)", 0, 100, int(pre.get("probabilidad", 25)), step=5)
            sem_def = pre.get("semana", week_label())
            sem = st.selectbox("Semana", SEMANAS, index=SEMANAS.index(sem_def) if sem_def in SEMANAS else 0)
        res = st.text_area("Resumen de la visita", value=pre.get("resumen", ""), height=120)
        if st.form_submit_button("Guardar reporte"):
            if cli.strip():
                db_exec(
                    "INSERT INTO bitacora (fecha, cliente, resumen, siguiente_paso, monto, moneda, probabilidad, semana) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (f.isoformat(), cli.strip(), res, sig, float(monto), mon, int(prob), sem),
                )
                st.session_state.pop("bitacora_prefill", None)
                st.success("Reporte guardado.")
                st.rerun()
            else:
                st.warning("Captura el cliente.")

    df = db_df("SELECT * FROM bitacora ORDER BY fecha DESC, id DESC")
    st.markdown("##### Historial")
    if df.empty:
        st.info("Aún no hay reportes.")
        return
    st.dataframe(df, width="stretch", hide_index=True)

    st.markdown("##### Editar o eliminar")
    ids = df["id"].tolist()
    sel = st.selectbox(
        "Reporte", ids,
        format_func=lambda i: str(i) + " | " + str(df.loc[df["id"] == i, "cliente"].iloc[0])
        + " | " + str(df.loc[df["id"] == i, "fecha"].iloc[0]),
        key="bt_sel",
    )
    r = df[df["id"] == sel].iloc[0]
    k = str(sel)
    with st.form("bit_edit_" + k):
        c1, c2 = st.columns(2)
        with c1:
            f = st.date_input("Fecha", value=parse_date_safe(r["fecha"]), key="bt_f_" + k)
            cli = st.text_input("Cliente", value=str(r["cliente"]), key="bt_c_" + k)
            sig = st.text_input("Siguiente paso", value=str(r["siguiente_paso"] or ""), key="bt_s_" + k)
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1000.0, value=float(r["monto"] or 0), key="bt_m_" + k)
            mon = st.selectbox("Moneda", MONEDAS,
                               index=MONEDAS.index(r["moneda"]) if r["moneda"] in MONEDAS else 0, key="bt_mo_" + k)
            try:
                p_val = max(0, min(100, int(r["probabilidad"])))
            except Exception:
                p_val = 0
            prob = st.slider("Probabilidad (%)", 0, 100, p_val, step=5, key="bt_p_" + k)
            sem = st.selectbox("Semana", SEMANAS,
                               index=SEMANAS.index(r["semana"]) if r["semana"] in SEMANAS else 0, key="bt_w_" + k)
        res = st.text_area("Resumen", value=str(r["resumen"] or ""), height=120, key="bt_r_" + k)
        u, d = st.columns(2)
        with u:
            do_upd = st.form_submit_button("Actualizar")
        with d:
            do_del = st.form_submit_button("Eliminar")
        if do_upd:
            db_exec(
                "UPDATE bitacora SET fecha=?, cliente=?, resumen=?, siguiente_paso=?, monto=?, moneda=?, "
                "probabilidad=?, semana=? WHERE id=?",
                (f.isoformat(), cli.strip(), res, sig, float(monto), mon, int(prob), sem, int(sel)),
            )
            st.rerun()
        if do_del:
            db_exec("DELETE FROM bitacora WHERE id=?", (int(sel),))
            st.rerun()


def render_forecast():
    df = db_df("SELECT * FROM bitacora")
    if df.empty:
        st.info("Registra reportes en la Bitácora para calcular el forecast.")
        return
    df["monto"] = pd.to_numeric(df["monto"], errors="coerce").fillna(0.0)
    df["probabilidad"] = pd.to_numeric(df["probabilidad"], errors="coerce").fillna(0.0)
    df["Forecast_Real"] = df["monto"] * (df["probabilidad"] / 100.0)

    tab = df.groupby(["semana", "moneda"]).agg(
        Registros=("id", "count"), Monto=("monto", "sum"), Forecast_Real=("Forecast_Real", "sum")
    ).reset_index()
    tab["semana"] = pd.Categorical(tab["semana"], categories=SEMANAS, ordered=True)
    tab = tab.sort_values(["semana", "moneda"]).rename(columns={"semana": "Semana", "moneda": "Moneda"})

    cols = st.columns(len(MONEDAS))
    for i, m in enumerate(MONEDAS):
        with cols[i]:
            val = float(tab.loc[tab["Moneda"] == m, "Forecast_Real"].sum())
            kpi_card("Forecast real " + m, fmt_money(val, m), "Monto x probabilidad")

    st.dataframe(tab.round(2), width="stretch", hide_index=True)
    ch = alt.Chart(tab).mark_bar().encode(
        x=alt.X("Semana:N", sort=SEMANAS, title=None),
        y=alt.Y("Forecast_Real:Q", title="Forecast real"),
        color=alt.Color("Moneda:N", scale=alt.Scale(range=[MESS_BLUE, ACCENT])),
        tooltip=["Semana", "Moneda", alt.Tooltip("Forecast_Real:Q", format=",.0f")],
    ).properties(height=260)
    show_chart(ch)


def render_reportes():
    ag = db_df("SELECT * FROM agenda ORDER BY fecha, hora")
    bt = db_df("SELECT * FROM bitacora ORDER BY fecha, id")
    clientes = sorted(set(ag["cliente"].tolist() + bt["cliente"].tolist()))
    if not clientes:
        st.info("Registra visitas o reportes para generar resúmenes.")
        return
    cli = st.selectbox("Cliente", clientes, key="rep_cli")
    a = ag[ag["cliente"] == cli]
    b = bt[bt["cliente"] == cli].copy()
    b["monto"] = pd.to_numeric(b["monto"], errors="coerce").fillna(0.0)
    b["probabilidad"] = pd.to_numeric(b["probabilidad"], errors="coerce").fillna(0.0)
    b["fc"] = b["monto"] * b["probabilidad"] / 100.0

    hoy = date.today().isoformat()
    txt = ["REPORTE COMERCIAL | " + cli, "Fecha: " + hoy,
           "Preparado por: Javier Camacho, Asesor B2B | MESS Servicios Metrológicos", "", "VISITAS"]
    md = ["## Reporte comercial | " + cli, "", "**Fecha:** " + hoy,
          "**Preparado por:** Javier Camacho, Asesor B2B | MESS Servicios Metrológicos", "", "### Visitas"]
    if a.empty:
        txt.append("- Sin visitas registradas.")
        md.append("- Sin visitas registradas.")
    for _, r in a.iterrows():
        line = str(r["fecha"]) + " " + str(r["hora"]) + " | " + str(r["estatus"])
        txt.append("- " + line)
        md.append("- " + line)
    txt += ["", "BITÁCORA"]
    md += ["", "### Bitácora"]
    if b.empty:
        txt.append("- Sin reportes registrados.")
        md.append("- Sin reportes registrados.")
    for _, r in b.iterrows():
        head = str(r["fecha"]) + " | " + str(r["semana"]) + " | " + format(r["monto"], ",.0f") + " " + str(r["moneda"]) + " al " + str(int(r["probabilidad"])) + "%"
        txt.append("- " + head)
        txt.append("  Resumen: " + str(r["resumen"] or ""))
        txt.append("  Siguiente paso: " + str(r["siguiente_paso"] or ""))
        md.append("- **" + head + "**")
        md.append("  - Resumen: " + str(r["resumen"] or ""))
        md.append("  - Siguiente paso: " + str(r["siguiente_paso"] or ""))
    txt += ["", "FORECAST"]
    md += ["", "### Forecast", "", "| Moneda | Monto | Forecast real |", "|---|---|---|"]
    for m in MONEDAS:
        sub = b[b["moneda"] == m]
        if sub.empty:
            continue
        txt.append("- " + m + ": monto " + format(sub["monto"].sum(), ",.0f") + ", forecast real " + format(sub["fc"].sum(), ",.0f"))
        md.append("| " + m + " | " + format(sub["monto"].sum(), ",.0f") + " | " + format(sub["fc"].sum(), ",.0f") + " |")
    txt_s, md_s = "\n".join(txt), "\n".join(md)

    t1, t2 = st.tabs(["Texto plano", "Markdown"])
    with t1:
        st.code(txt_s, language="text")
        st.download_button("Descargar .txt", txt_s, file_name="Reporte_" + re.sub(r"\W+", "_", cli) + ".txt")
    with t2:
        st.code(md_s, language="markdown")
        st.download_button("Descargar .md", md_s, file_name="Reporte_" + re.sub(r"\W+", "_", cli) + ".md")
    st.link_button(
        "Abrir en correo",
        "mailto:?subject=" + quote("Reporte comercial | " + cli) + "&body=" + quote(txt_s[:1800]),
    )


def render_revops():
    st.subheader("Gestión comercial (RevOps)")
    sa, sb, sc, sd = st.tabs(["Agenda", "Bitácora", "Forecast", "Reportes"])
    with sa:
        render_agenda()
    with sb:
        render_bitacora()
    with sc:
        render_forecast()
    with sd:
        render_reportes()


# ---------------------------------------------------------------------------
# SIDEBAR Y FLUJO PRINCIPAL
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### SAIV")
    st.caption("Radar Comercial MESS")
    archivo = st.file_uploader("CSV del CRM (SCOTT)", type=["csv"])
    meta = st.number_input("Meta mensual (USD)", min_value=0.0, value=80000.0, step=5000.0)
    tc = st.number_input("Tipo de cambio MXN por USD", min_value=1.0, value=18.0, step=0.1)
    if st.button("Cerrar sesión"):
        st.session_state.clear()
        st.rerun()

st.title("SAIV | Radar Comercial MESS")
st.caption("Sistema Automatizado de Ingeniería de Ventas")

crm = None
if archivo is not None:
    try:
        crm, avisos = load_crm(archivo.getvalue())
        for a_ in avisos:
            st.warning(a_)
        if crm is not None:
            crm = crm.copy()
            crm["Total_USD_Eq"] = crm["Monto_USD"] + crm["Monto_MXN"] / tc
    except Exception as e:
        st.error("No se pudo procesar el CSV: " + str(e))
        crm = None

tab1, tab2, tab3, tab4 = st.tabs([
    "Dashboards CRM", "Proyectos Estancados", "Laboratorio Táctico IA", "Gestión Comercial",
])

with tab1:
    try:
        render_dashboard(crm, meta, tc)
    except Exception as e:
        st.error("Error en Dashboards: " + str(e))
with tab2:
    try:
        render_stalled(crm)
    except Exception as e:
        st.error("Error en Proyectos Estancados: " + str(e))
with tab3:
    try:
        render_lab(crm)
    except Exception as e:
        st.error("Error en Laboratorio Táctico: " + str(e))
with tab4:
    try:
        render_revops()
    except Exception as e:
        st.error("Error en Gestión Comercial: " + str(e))
