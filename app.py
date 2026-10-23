# -*- coding: utf-8 -*-
"""
SAIV | Radar Comercial MESS  (v2.1: pipeline vivo + Laboratorio IA + ABM / Marketing)

Secrets (.streamlit/secrets.toml):
    mi_contrasena  = "tu_contraseña"
    gemini_api_key = "tu_api_key"
    gemini_model   = "gemini-3.8-flash"   # opcional; cambia aquí el modelo sin tocar el código
"""

import csv
import hmac
import io
import re
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
except Exception:
    Document = None

# ---------------------------------------------------------------------------
# CONSTANTES EDITABLES
# ---------------------------------------------------------------------------
MESS_BLUE = "#003a70"
MESS_DARK = "#2c3e50"
ACCENT = "#ff6600"
RED = "#c0392b"

DEFAULT_MODEL = "gemini-3.8-flash"

FASES = {
    0: "0. Sin clasificar",
    1: "1. Propuesta",
    2: "2. Cotización",
    3: "3. Negociación",
    4: "4. Esperando PO",
}
PROB_DEFAULT = {1: 10, 2: 25, 3: 50, 4: 80}
UMBRAL_DIAS = {0: 60, 1: 30, 2: 45, 3: 75, 4: 45}

SIGUIENTE_PASO = {
    0: "Revisar la etapa en SCOTT",
    1: "Validar necesidad y decisor; preparar cotización",
    2: "Confirmar recepción y criterios de decisión",
    3: "Resolver objeciones y fijar fecha de decisión",
    4: "Confirmar fecha de colocación de la PO",
}
OBJETIVO_FASE = {
    0: "Reactivar proyecto frío",
    1: "Calificar necesidad y decisor",
    2: "Dar seguimiento a cotización",
    3: "Manejar objeciones y fijar fecha de decisión",
    4: "Asegurar colocación de PO",
}
OBJETIVOS = [
    "Calificar necesidad y decisor",
    "Dar seguimiento a cotización",
    "Manejar objeciones y fijar fecha de decisión",
    "Asegurar colocación de PO",
    "Reactivar proyecto frío",
    "Ampliar la cuenta (cross-selling)",
    "Agendar visita técnica",
    "Desplegar campaña ABM / Marketing digital específico",
]
FOCO_MEDDPICC = {
    0: "validar si el proyecto sigue vivo y quién decide",
    1: "validar el dolor (Pain), al Champion y al comprador económico",
    2: "validar criterios de decisión (Decision Criteria) y competencia",
    3: "validar proceso de decisión (Decision Process), papeleo y comprador económico",
    4: "validar el proceso de compra interno y la fecha real de colocación de la PO",
}
DIAS_FRESCO = 25
CANALES = ["WhatsApp", "Correo ejecutivo", "Llamada", "Visita presencial"]
PERFILES = ["Ingeniero de planta o calidad", "Comprador", "Director o dueño"]

ALIAS_CUENTAS = ["CNH", "SAFRAN", "ITP", "SIEMENS ENERGY", "ADIENT", "BROSE", "DANA", "STEERINGMEX"]

# ---------------------------------------------------------------------------
# PÁGINA Y ESTILOS
# ---------------------------------------------------------------------------
st.set_page_config(page_title="SAIV | Radar Comercial MESS", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp, button, input, textarea, select {
    font-family: 'Montserrat', sans-serif !important;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stApp { background-color: #f8fafc; }
h1, h2, h3, h4 { color: #003a70; font-weight: 700; }
.header-mess {
    background: linear-gradient(135deg, #003a70 0%, #002244 100%);
    padding: 22px 28px; border-radius: 10px; color: #ffffff; margin-bottom: 18px;
    border-left: 6px solid #ff6600; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}
.header-mess h1 { color: #ffffff; font-size: 24px; font-weight: 800; margin: 0; text-transform: uppercase; }
.header-mess p { font-size: 12px; margin: 4px 0 0 0; color: #cbd5e1; text-transform: uppercase; letter-spacing: 1px; }
.kpi-card {
    background: #ffffff; border: 1px solid #e2e8f0; border-left: 6px solid #003a70;
    border-radius: 8px; padding: 12px 16px; box-shadow: 0 2px 6px rgba(0,58,112,0.08); margin-bottom: 10px;
}
.kpi-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: #2c3e50; font-weight: 600; }
.kpi-value { font-size: 1.5rem; font-weight: 700; color: #003a70; line-height: 1.2; }
.kpi-sub { font-size: 0.72rem; color: #64748b; }
.stButton > button { background-color: #003a70; color: #ffffff; border: none; border-radius: 6px; font-weight: 600; }
.stButton > button:hover { background-color: #002a52; color: #ffffff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SEGURIDAD
# ---------------------------------------------------------------------------
def check_password():
    if st.session_state.get("auth_ok"):
        return True
    st.sidebar.markdown("### Acceso restringido")
    try:
        secret = str(st.secrets["mi_contrasena"])
    except Exception:
        secret = ""
    if not secret:
        st.sidebar.error("Falta 'mi_contrasena' en st.secrets. La app permanece bloqueada.")
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
    st.info("Ingresa tu contraseña en el menú lateral para continuar.")
    st.stop()

st.markdown(
    '<div class="header-mess"><h1>MESS Servicios Metrológicos</h1>'
    "<p>SAIV | Radar Comercial y Copiloto KAM</p></div>",
    unsafe_allow_html=True,
)


# ===========================================================================
# LÓGICA DE DATOS (inicio)
# ===========================================================================
def norm(text):
    s = "" if text is None else str(text)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper().strip()


def decode_bytes(raw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def detect_delimiter(text):
    try:
        return csv.Sniffer().sniff(text[:5000], delimiters=",;\t|").delimiter
    except Exception:
        return ","


REPARACIONES = [
    ("ci?n", "ción"), ("CI?N", "CIÓN"), ("Ci?n", "Ción"),
    ("?xico", "éxico"), ("?XICO", "ÉXICO"),
    ("aut?nom", "autónom"), ("AUT?NOM", "AUTÓNOM"), ("Aut?nom", "Autónom"),
    ("se?o", "seño"), ("SE?O", "SEÑO"), ("Se?o", "Seño"),
    ("a?o", "año"), ("A?O", "AÑO"),
    ("metr?a", "metría"), ("METR?A", "METRÍA"), ("Metr?a", "Metría"),
    ("?ptic", "óptic"), ("?PTIC", "ÓPTIC"), ("?ptic", "Óptic"),
]


def reparar_texto(x):
    t = "" if x is None else str(x)
    for a, b in REPARACIONES:
        t = t.replace(a, b)
    return re.sub(r"^\?+(?=[A-Za-zÁÉÍÓÚÑáéíóúñ])", "", t).strip()


def parse_valor(v):
    s = "" if v is None else str(v)
    m = re.search(r"-?\d[\d,]*\.?\d*", s)
    try:
        amt = float(m.group().replace(",", "")) if m else 0.0
    except ValueError:
        amt = 0.0
    up = s.upper()
    cur = "USD" if ("USD" in up or "US$" in up) else "MXN"
    return amt, cur


def classify_fase(etapa):
    t = norm(etapa)
    if re.search(r"ESPERANDO|\bPO\b|ORDEN DE COMPRA", t):
        return 4
    if "NEGOCI" in t:
        return 3
    if "COTIZ" in t:
        return 2
    if "PROPUESTA" in t:
        return 1
    return 0


def tipo_de_area(area):
    a = norm(area)
    if a.startswith("VENTAS"):
        return "Equipos y consumibles"
    if a.startswith(("LABORATORIO", "SERVICIOS")) or "DIMENSIONAL" in a or "CALIBRAC" in a:
        return "Servicios y laboratorio"
    return "Otros (revisar)"


def cuenta_de(cliente):
    n = norm(cliente)
    for key in ALIAS_CUENTAS:
        if n == key or n.startswith(key + " "):
            return key
    return n


@st.cache_data(show_spinner=False)
def load_pipeline(raw_bytes, hoy_iso):
    avisos = []
    hoy = pd.Timestamp(hoy_iso)
    text = decode_bytes(raw_bytes)
    rows = list(csv.reader(io.StringIO(text), delimiter=detect_delimiter(text)))

    h = None
    for i, r in enumerate(rows):
        joined = " ".join(norm(c) for c in r)
        if "PROYECTO" in joined and "CLIENTE" in joined:
            h = i
            break
    if h is None:
        return None, ["No se encontró la fila de encabezados con PROYECTO y CLIENTE."]

    header = [norm(c) for c in rows[h]]

    def find(*keys):
        for k in keys:
            for pos, n in enumerate(header):
                if k in n:
                    return pos
        return None

    pos = {
        "proy": find("PROYECTO", "FOLIO"),
        "reg": find("FECHA DE REGISTRO"),
        "desc": find("DESCRIPCION"),
        "cli": find("CLIENTE"),
        "area": find("AREA"),
        "cierre": find("FECHA DE CIERRE"),
        "valor": find("VALOR", "MONTO", "IMPORTE"),
        "cot": find("COTIZACION"),
        "etapa": find("ETAPA", "FASE"),
        "estatus": find("ESTATUS", "STATUS"),
    }
    if pos["proy"] is None or pos["cli"] is None:
        return None, ["No se pudieron identificar las columnas PROYECTO y CLIENTE."]
    if pos["valor"] is None:
        avisos.append("No se encontró la columna VALOR; los montos quedan en cero.")
    if pos["etapa"] is None:
        avisos.append("No se encontró la columna ETAPA; todo queda sin clasificar.")

    def cell(r, key):
        p = pos.get(key)
        if p is None or p >= len(r):
            return ""
        return str(r[p]).strip()

    recs = []
    cur = None
    for r in rows[h + 1:]:
        if not any(str(c).strip() for c in r):
            continue
        folio = cell(r, "proy")
        if folio:
            cur = {
                "Folio": folio,
                "Registro_txt": cell(r, "reg"),
                "Descripcion": cell(r, "desc"),
                "Cliente": cell(r, "cli"),
                "Razon_Social": "",
                "Area": cell(r, "area"),
                "Cierre_txt": cell(r, "cierre"),
                "Valor_txt": cell(r, "valor"),
                "Cotizacion": cell(r, "cot"),
                "Etapa": cell(r, "etapa"),
                "Estatus": cell(r, "estatus"),
            }
            recs.append(cur)
        elif cur is not None:
            rs = cell(r, "cli")
            if rs and not cur["Razon_Social"]:
                cur["Razon_Social"] = rs

    if not recs:
        return None, ["El archivo no contiene proyectos debajo de los encabezados."]

    d = pd.DataFrame(recs)
    d = d.drop_duplicates(subset="Folio", keep="first").reset_index(drop=True)
    for c in ("Descripcion", "Cliente", "Razon_Social", "Area"):
        d[c] = d[c].map(reparar_texto)

    sin_cli = d["Cliente"].map(lambda x: norm(x) in ("", "DIRECCION FISCAL"))
    if sin_cli.any():
        d.loc[sin_cli, "Cliente"] = d.loc[sin_cli, "Razon_Social"].replace("", "SIN CLIENTE")
        avisos.append(str(int(sin_cli.sum())) + " proyecto(s) sin nombre de cliente válido; se usó la razón social.")

    vals = d["Valor_txt"].map(parse_valor)
    d["Monto_USD"] = [a if c == "USD" else 0.0 for a, c in vals]
    d["Monto_MXN"] = [a if c == "MXN" else 0.0 for a, c in vals]
    d["Sin_Cotizar"] = (d["Monto_USD"] == 0) & (d["Monto_MXN"] == 0)

    d["Cotizacion"] = d["Cotizacion"].map(lambda x: "" if norm(x) in ("", "SIN REGISTRO") else x)
    d["Fase_Num"] = d["Etapa"].map(classify_fase)
    d["Fase"] = d["Fase_Num"].map(FASES)
    n_sin_clasif = int((d["Fase_Num"] == 0).sum())
    if n_sin_clasif:
        avisos.append(str(n_sin_clasif) + " proyecto(s) con etapa no reconocida quedaron como 'Sin clasificar'.")

    d["Tipo"] = d["Area"].map(tipo_de_area)
    d["Cuenta"] = d["Cliente"].map(cuenta_de)

    d["Registro"] = pd.to_datetime(d["Registro_txt"], dayfirst=True, errors="coerce")
    d["Cierre_Est"] = pd.to_datetime(d["Cierre_txt"], dayfirst=True, errors="coerce")
    n_sin_fecha = int(d["Registro"].isna().sum())
    if n_sin_fecha:
        avisos.append(str(n_sin_fecha) + " proyecto(s) sin fecha de registro válida; su antigüedad se toma como 0.")
    d["Dias_Registro"] = (hoy - d["Registro"].dt.normalize()).dt.days.fillna(0).astype(int)
    d["Dias_a_Cierre"] = (d["Cierre_Est"].dt.normalize() - hoy).dt.days

    return d, avisos


def enrich(df, tc, probs, rates):
    d = df.copy()
    d["Total_USD_Eq"] = d["Monto_USD"] + d["Monto_MXN"] / tc
    d["Prob"] = d["Fase_Num"].map(lambda f: probs.get(int(f), 10) / 100.0)
    d["Ponderado"] = d["Total_USD_Eq"] * d["Prob"]
    d["Tasa_Com"] = d["Tipo"].map(lambda t: rates.get(t, 0.0) / 100.0)
    d["Comision_Est"] = d["Ponderado"] * d["Tasa_Com"]

    alertas, semaforos = [], []
    for _, r in d.iterrows():
        flags = []
        if r["Sin_Cotizar"]:
            flags.append("Cotizar")
        dc = r["Dias_a_Cierre"]
        if pd.notna(dc) and dc < 0:
            flags.append("Cierre vencido")
        u = UMBRAL_DIAS.get(int(r["Fase_Num"]), 60)
        if r["Dias_Registro"] > 2 * u:
            flags.append("Depurar")
        elif r["Dias_Registro"] > u:
            flags.append("Dar seguimiento")
        alertas.append(", ".join(flags))
        if "Cierre vencido" in flags or "Depurar" in flags:
            semaforos.append("Rojo")
        elif flags:
            semaforos.append("Ámbar")
        else:
            semaforos.append("Verde")
    d["Alerta"] = alertas
    d["Semaforo"] = semaforos
    d["Siguiente_Paso"] = [
        "Cotizar y enviar al cliente" if s else SIGUIENTE_PASO.get(int(f), "")
        for s, f in zip(d["Sin_Cotizar"], d["Fase_Num"])
    ]
    return d


# ===========================================================================
# LÓGICA DE DATOS (fin)
# ===========================================================================


def fmt_usd(x):
    try:
        return "$" + format(float(x), ",.0f")
    except Exception:
        return "$0"


def show_chart(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:
        st.altair_chart(chart, use_container_width=True)


def kpi_card(label, value, sub=""):
    st.markdown(
        '<div class="kpi-card"><div class="kpi-label">' + label + "</div>"
        '<div class="kpi-value">' + value + "</div>"
        '<div class="kpi-sub">' + sub + "</div></div>",
        unsafe_allow_html=True,
    )


DISPLAY = {
    "Monto_USD": "USD",
    "Monto_MXN": "MXN",
    "Total_USD_Eq": "Total Eq. USD",
    "Ponderado": "Ponderado USD",
    "Comision_Est": "Comisión est. USD",
    "Dias_Registro": "Días reg.",
    "Dias_a_Cierre": "Días a cierre",
    "Cierre_Est": "Cierre est.",
    "Siguiente_Paso": "Siguiente paso",
    "Semaforo": "Semáforo",
    "Descripcion": "Descripción",
    "Cotizacion": "Cotización",
    "Fase": "Fase",
}
SEMAFORO_CSS = {
    "Rojo": "color:#c0392b;font-weight:700",
    "Ámbar": "color:#b9770e;font-weight:700",
    "Verde": "color:#1e8449;font-weight:700",
}


def show_table(d, cols, key=None):
    if d is None or d.empty:
        st.info("Sin registros para esta vista.")
        return
    t = d[cols].copy()
    if "Descripcion" in t.columns:
        t["Descripcion"] = t["Descripcion"].astype(str).str.slice(0, 70)
    if "Cierre_Est" in t.columns:
        t["Cierre_Est"] = t["Cierre_Est"].dt.strftime("%d/%m/%Y").fillna("")
    t = t.rename(columns=DISPLAY)
    fmt = {}
    for c in ("USD", "MXN"):
        if c in t.columns:
            fmt[c] = "${:,.2f}"
    for c in ("Total Eq. USD", "Ponderado USD", "Comisión est. USD"):
        if c in t.columns:
            fmt[c] = "${:,.0f}"
    sty = t.style.format(fmt, na_rep="")
    if "Semáforo" in t.columns:
        try:
            sty = sty.map(lambda v: SEMAFORO_CSS.get(v, ""), subset=["Semáforo"])
        except AttributeError:
            sty = sty.applymap(lambda v: SEMAFORO_CSS.get(v, ""), subset=["Semáforo"])
    try:
        st.dataframe(sty, hide_index=True, width="stretch")
    except TypeError:
        st.dataframe(sty, hide_index=True, use_container_width=True)


def totals_caption(d):
    if d is None or d.empty:
        return
    st.caption(
        "Totales de esta vista: " + str(len(d)) + " proyectos | USD "
        + format(d["Monto_USD"].sum(), ",.2f") + " | MXN " + format(d["Monto_MXN"].sum(), ",.2f")
        + " | Total equivalente USD " + format(d["Total_USD_Eq"].sum(), ",.0f")
    )


# ---------------------------------------------------------------------------
# IA (GEMINI)
# ---------------------------------------------------------------------------
def call_gemini(prompt):
    if genai is None:
        return None, "Falta instalar la librería google-generativeai."
    key = None
    model_name = DEFAULT_MODEL
    try:
        key = st.secrets.get("gemini_api_key") or st.secrets.get("GEMINI_API_KEY")
        model_name = st.secrets.get("gemini_model") or DEFAULT_MODEL
    except Exception:
        pass
    if not key:
        return None, "Falta 'gemini_api_key' en st.secrets."
    try:
        genai.configure(api_key=key)
        resp = genai.GenerativeModel(model_name).generate_content(prompt)
        return resp.text, None
    except Exception as e:
        return None, "Error al consultar Gemini (" + model_name + "): " + str(e)


def parse_tags(text):
    out = {}
    for tag in ["ANALYSIS", "MESSAGE", "OBJECTIONS", "MARKETING", "LOG"]:
        pat = "<" + tag + ">(.*?)(?=</" + tag + ">|<[A-Z]+>|$)"
        m = re.search(pat, text or "", re.S | re.I)
        out[tag] = m.group(1).strip() if m else ""
    return out


def build_prompt(ctx):
    montos = []
    if ctx["usd"] > 0:
        montos.append(format(ctx["usd"], ",.2f") + " USD")
    if ctx["mxn"] > 0:
        montos.append(format(ctx["mxn"], ",.2f") + " MXN")
    monto_txt = " y ".join(montos) if montos else "Aún sin cotizar (sin monto): no menciones precios en el mensaje."
    lines = [
        "Actúa como Javier Camacho, Key Account Manager (KAM) B2B de MESS Servicios Metrológicos en Querétaro, México.",
        "Eres experto en metrología dimensional, calibración acreditada ISO/IEC 17025 y equipos de alta gama (Zeiss, Taylor Hobson, Wilson, Kreon).",
        "Hablas como asesor técnico de metrología industrial: trazabilidad, incertidumbre, repetibilidad, paros de línea, retrabajo y certeza dimensional en piso de producción.",
        "Tono consultivo, humano y directo, sin exageraciones técnicas ni lenguaje de marketing inflado. Frases claras y cortas.",
        "No inventes precios, fechas de entrega, certificaciones, referencias ni datos que no estén en el contexto.",
        "",
        "DATOS DE LA OPORTUNIDAD:",
        "- Cuenta: " + ctx["cuenta"],
        "- Folios agrupados: " + ctx["folios"],
        "- Descripción de equipos o servicios: " + ctx["descripcion"],
        "- Monto del paquete: " + monto_txt,
        "- Fase actual: " + ctx["fase"],
        "- Días desde el registro: " + str(ctx["dias"]),
        "- Cierre estimado en SCOTT: " + ctx["cierre"],
        "- Cotizaciones: " + (ctx["cotizaciones"] or "Sin número de cotización registrado"),
        "- Propuestas a incluir:",
        ctx["desglose"],
        "- Objetivo de esta acción: " + ctx["objetivo"],
        "- Canal: " + ctx["canal"],
        "- Interlocutor: " + ctx["perfil"],
        "- Giro industrial: " + (ctx["giro"] or "No especificado"),
        "- Contexto adicional: " + (ctx["contexto"] or "Ninguno"),
        "",
        "METODOLOGÍA (aplícala de forma invisible y natural):",
        "- SPIN Selling: preguntas de Situación, Problema, Implicación y Necesidad-Solución sobre el riesgo de medir mal o calibrar tarde.",
        "- MEDDPICC: en esta fase el foco es " + ctx["foco"] + ". Señala qué elementos faltan por validar y qué pregunta los destapa.",
        "- Sandler: dale al cliente permiso de decir que no, sin presión y sin forzar una decisión. Busca una respuesta honesta, no una promesa.",
        "- Account-Based Marketing (ABM): propón tácticas de marketing digital o de guerrilla enfocadas específicamente a esta cuenta para influir en los tomadores de decisiones.",
        "",
        "FORMATO: responde ÚNICAMENTE con estas cinco etiquetas XML, en este orden, sin texto fuera de ellas y sin bloques de código:",
        "<ANALYSIS> Diagnóstico breve: qué sabemos, qué falta validar (lista corta MEDDPICC) y la mejor jugada para esta fase. </ANALYSIS>",
        "<MESSAGE> Dos versiones listas para enviar por el canal indicado, separadas por una línea con tres guiones (---): primero la versión BREVE y después la COMPLETA. Incluye al menos una pregunta SPIN y un cierre con permiso de decir no. </MESSAGE>",
        "REGLAS PARA <MESSAGE>: el texto se mostrará en una caja de texto plano. PROHIBIDO usar tablas Markdown (nada de barras verticales ni :---) y PROHIBIDO usar asteriscos.",
        "En la versión COMPLETA presenta cada propuesta en una lista vertical, con una línea en blanco entre propuestas, con este formato exacto:",
        "• Cotización [Número] - [Equipo o servicio]",
        "Impacto en planta: [beneficio técnico metrológico o cumplimiento normativo IATF/ISO, sin inventar certificaciones adicionales]",
        "Inversión: [monto exacto en USD o MXN; si no hay monto escribe 'Por cotizar']",
        "La versión BREVE no lleva la lista: solo menciona el paquete y una pregunta.",
        "<OBJECTIONS> Las dos o tres objeciones más probables (precio, tiempos, prioridad interna) y cómo responderlas con enfoque Sandler. </OBJECTIONS>",
        "<MARKETING> Acciones de marketing digital o tácticas ABM recomendadas para esta cuenta (ej. envío de casos de éxito técnicos, whitepapers de metrología o invitación personalizada). </MARKETING>",
        "<LOG> Resumen de dos a cuatro líneas para registrar en SCOTT: acción, interlocutor y siguiente paso. </LOG>",
    ]
    return "\n".join(lines)


def clean_message(txt):
    out = []
    for line in str(txt or "").replace("**", "").splitlines():
        if re.match(r"^\s*\|.*\|\s*$", line) or re.match(r"^\s*:?-{3,}:?(\s*\|\s*:?-{3,}:?)+\s*$", line):
            continue
        out.append(line.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def whatsapp_link(message, phone=""):
    digits = re.sub(r"\D", "", phone or "")
    base_url = "https://wa.me/" + digits if digits else "https://wa.me/"
    return base_url + "?text=" + quote(message or "")


def gcal_link(title, details, start_dt, minutes=30):
    end_dt = start_dt + timedelta(minutes=minutes)
    f = "%Y%m%dT%H%M%S"
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + quote(title)
        + "&details=" + quote((details or "")[:1500])
        + "&dates=" + start_dt.strftime(f) + "/" + end_dt.strftime(f)
    )


def build_docx(ctx, tags, mensaje, log_txt):
    doc = Document()
    doc.add_heading("Estrategia KAM | MESS Servicios Metrológicos", 0)
    doc.add_paragraph("Cuenta: " + ctx["cuenta"] + "\nFolios: " + ctx["folios"]
                      + "\nFecha: " + datetime.now().strftime("%d/%m/%Y"))
    doc.add_paragraph("Fase: " + ctx["fase"] + " | Objetivo: " + ctx["objetivo"] + " | Canal: " + ctx["canal"])
    doc.add_paragraph("USD: " + format(ctx["usd"], ",.2f") + " | MXN: " + format(ctx["mxn"], ",.2f"))
    doc.add_paragraph("Cotizaciones: " + (ctx["cotizaciones"] or "N/D") + "\n" + ctx["desglose"])
    for titulo, txt in [
        ("Análisis", tags.get("ANALYSIS", "")),
        ("Mensaje", mensaje),
        ("Manejo de objeciones", tags.get("OBJECTIONS", "")),
        ("Acciones de Marketing / ABM", tags.get("MARKETING", "")),
        ("Registro para SCOTT", log_txt),
    ]:
        doc.add_heading(titulo, level=2)
        doc.add_paragraph(txt or "Sin contenido.")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# SIDEBAR: DATOS, PARÁMETROS Y FILTROS
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Carga de datos")
    archivo = st.file_uploader("Extracción CSV de SCOTT", type=["csv"])

    st.markdown("### Parámetros")
    tc = st.number_input("Tipo de cambio (MXN por USD)", min_value=1.0, value=18.0, step=0.5)
    meta = st.number_input("Meta mensual (USD)", min_value=0.0, value=80000.0, step=5000.0)
    cerrado = st.number_input(
        "Cerrado del mes (USD, de tu otra app)", min_value=0.0, value=0.0, step=1000.0,
        help="Los ganados no vienen en este CSV; captúralo para calcular faltante y cobertura.",
    )
    with st.expander("Probabilidad por fase (%)"):
        probs = {
            1: st.number_input("Propuesta", 0, 100, PROB_DEFAULT[1], step=5),
            2: st.number_input("Cotización", 0, 100, PROB_DEFAULT[2], step=5),
            3: st.number_input("Negociación", 0, 100, PROB_DEFAULT[3], step=5),
            4: st.number_input("Esperando PO", 0, 100, PROB_DEFAULT[4], step=5),
        }
    with st.expander("Comisión estimada (opcional, %)"):
        st.caption("Captura tu tasa efectiva por tipo. Con cero no se muestra la columna.")
        rates = {
            "Equipos y consumibles": st.number_input("Equipos y consumibles", 0.0, 100.0, 0.0, step=0.5),
            "Servicios y laboratorio": st.number_input("Servicios y laboratorio", 0.0, 100.0, 0.0, step=0.5),
            "Otros (revisar)": st.number_input("Otros", 0.0, 100.0, 0.0, step=0.5),
        }

hoy = pd.Timestamp.today().normalize()
base = None
avisos = []
if archivo is not None:
    try:
        raw_df, avisos = load_pipeline(archivo.getvalue(), hoy.strftime("%Y-%m-%d"))
        if raw_df is not None:
            base = enrich(raw_df, tc, probs, rates)
        else:
            st.sidebar.error("; ".join(avisos))
    except Exception as e:
        st.sidebar.error("No se pudo procesar el CSV: " + str(e))

df = pd.DataFrame()
if base is not None:
    with st.sidebar:
        st.markdown("### Búsqueda y filtros")
        f_txt = st.text_input("Buscar", placeholder="Cliente, folio, equipo, marca, cotización...")
        f_fase = st.multiselect("Fase", [FASES[i] for i in sorted(base["Fase_Num"].unique())])
        f_tipo = st.multiselect("Tipo", sorted(base["Tipo"].unique()))
        f_area = st.multiselect("Área o marca", sorted(base["Area"].unique()))
        f_cuenta = st.multiselect("Cuenta", sorted(base["Cuenta"].unique()))
        f_min = st.number_input("Monto mínimo (USD eq.)", min_value=0, value=0, step=1000)
        f_dias = st.number_input("Antigüedad mínima (días)", min_value=0, value=0, step=15)
        f_frescos = st.checkbox("Solo en tiempo (menos de " + str(DIAS_FRESCO) + " días)")
        f_rezag = st.checkbox("Solo rezagados (" + str(DIAS_FRESCO) + " días o más)")
        f_sin_cot = st.checkbox("Solo sin cotizar")
        f_riesgo = st.checkbox("Solo en rojo (cierre vencido o por depurar)")

    df = base.copy()
    if f_txt:
        needle = f_txt.strip().lower()
        hay = (
            df["Cliente"].astype(str) + " " + df["Razon_Social"].astype(str) + " " + df["Folio"].astype(str)
            + " " + df["Descripcion"].astype(str) + " " + df["Area"].astype(str) + " " + df["Cotizacion"].astype(str)
        ).str.lower()
        df = df[hay.str.contains(needle, regex=False)]
    if f_fase:
        df = df[df["Fase"].isin(f_fase)]
    if f_tipo:
        df = df[df["Tipo"].isin(f_tipo)]
    if f_area:
        df = df[df["Area"].isin(f_area)]
    if f_cuenta:
        df = df[df["Cuenta"].isin(f_cuenta)]
    if f_min > 0:
        df = df[df["Total_USD_Eq"] >= f_min]
    if f_dias > 0:
        df = df[df["Dias_Registro"] >= f_dias]
    if f_frescos:
        df = df[df["Dias_Registro"] < DIAS_FRESCO]
    if f_rezag:
        df = df[df["Dias_Registro"] >= DIAS_FRESCO]
    if f_sin_cot:
        df = df[df["Sin_Cotizar"]]
    if f_riesgo:
        df = df[df["Semaforo"] == "Rojo"]
    st.sidebar.caption("Mostrando " + str(len(df)) + " de " + str(len(base)) + " proyectos")

hay_comision = any(v > 0 for v in rates.values())

tab_dash, tab_lab = st.tabs(["Dashboard de Oportunidades", "Laboratorio IA"])


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
def render_dashboard():
    if base is None:
        st.info("Sube la extracción CSV de SCOTT en el panel lateral para ver tu pipeline.")
        return
    for a in avisos:
        st.warning(a)
    if df.empty:
        st.info("Ningún proyecto coincide con los filtros activos.")
        return

    n_usd = int((df["Monto_USD"] > 0).sum())
    n_mxn = int((df["Monto_MXN"] > 0).sum())
    c1, c2, c3 = st.columns(3)
    with c1:
        kpi_card("Pipeline en USD", "$" + format(df["Monto_USD"].sum(), ",.2f"), str(n_usd) + " proyectos con monto en USD")
    with c2:
        kpi_card("Pipeline en MXN", "$" + format(df["Monto_MXN"].sum(), ",.2f"), str(n_mxn) + " proyectos con monto en MXN")
    with c3:
        kpi_card("Total equivalente USD", fmt_usd(df["Total_USD_Eq"].sum()), "Tipo de cambio " + str(tc))

    fin_mes = hoy + pd.offsets.MonthEnd(0)
    mes = df[df["Cierre_Est"] <= fin_mes]
    ponderado = float(df["Ponderado"].sum())
    faltante = max(0.0, meta - cerrado)
    cobertura = (ponderado / faltante) if faltante > 0 else None

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        kpi_card("Probable (ponderado)", fmt_usd(ponderado), "Monto por probabilidad de fase")
    with k2:
        kpi_card("Cierre estimado este mes", fmt_usd(mes["Total_USD_Eq"].sum()),
                 str(len(mes)) + " proyectos | ponderado " + fmt_usd(mes["Ponderado"].sum()))
    with k3:
        kpi_card("Faltante para la meta", fmt_usd(faltante), "Meta " + fmt_usd(meta) + " menos cerrado " + fmt_usd(cerrado))
    with k4:
        kpi_card("Cobertura de pipeline", (format(cobertura, ".1f") + "x") if cobertura is not None else "Meta cubierta",
                 "Probable entre faltante")

    top_date = df["Cierre_Est"].value_counts()
    if len(top_date) and top_date.iloc[0] / len(df) >= 0.30:
        st.warning(
            str(round(top_date.iloc[0] / len(df) * 100)) + "% de los proyectos comparten la fecha de cierre estimada "
            + top_date.index[0].strftime("%d/%m/%Y")
            + ". Si es una fecha por defecto de SCOTT, el cierre estimado del mes está sobrestimado."
        )
    st.caption("La antigüedad se mide desde la fecha de registro; el CSV no trae fecha del último movimiento.")

    vista = st.radio("Vista de gráficas", ["Global (USD equivalente)", "Solo USD", "Solo MXN"], horizontal=True)
    if vista.startswith("Global"):
        dv, col, cur = df, "Total_USD_Eq", "USD eq."
    elif vista == "Solo USD":
        dv, col, cur = df[df["Monto_USD"] > 0], "Monto_USD", "USD"
    else:
        dv, col, cur = df[df["Monto_MXN"] > 0], "Monto_MXN", "MXN"
    dv = dv.assign(Valor_Vista=dv[col], Pond_Vista=dv[col] * dv["Prob"])

    st.markdown("### Dónde actuar hoy")
    cols_base = ["Folio", "Cliente", "Descripcion", "Fase", "Monto_USD", "Monto_MXN", "Total_USD_Eq",
                 "Ponderado", "Cierre_Est", "Dias_Registro", "Alerta", "Siguiente_Paso"]
    cols_top = list(cols_base)
    orden = "Ponderado"
    if hay_comision:
        cols_top.insert(8, "Comision_Est")
        orden = "Comision_Est"
    t1, t2, t3, t4 = st.tabs([
        "Top 10 valor esperado", "Cierre próximo o vencido", "Por cotizar", "Por depurar o rescatar",
    ])
    with t1:
        st.caption("Ordenado por " + ("comisión estimada." if hay_comision else "monto ponderado por probabilidad de fase."))
        show_table(df[df["Total_USD_Eq"] > 0].sort_values(orden, ascending=False).head(10), cols_top)
    with t2:
        prox = df[df["Dias_a_Cierre"] <= 7].sort_values("Dias_a_Cierre")
        st.caption("Proyectos con cierre estimado en los próximos 7 días o ya vencido.")
        show_table(prox.head(25), cols_base)
    with t3:
        pend = df[df["Sin_Cotizar"]].sort_values("Dias_Registro", ascending=False)
        st.caption("Proyectos con valor 0.00: aún no hay monto cotizado. Sin cotización no hay cierre.")
        show_table(pend.head(30), ["Folio", "Cliente", "Descripcion", "Fase", "Area", "Dias_Registro", "Cierre_Est", "Siguiente_Paso"])
    with t4:
        rojo = df[df["Semaforo"] == "Rojo"].sort_values("Total_USD_Eq", ascending=False)
        st.caption("Cierre vencido o antigüedad mayor al doble de lo esperado para su fase. Candidatos a rescate (cierre negativo de Sandler) o a cerrar en SCOTT.")
        show_table(rojo.head(30), cols_base)

    st.markdown("### Concentración y embudo (" + cur + ")")
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Pareto 80/20 por cuenta**")
        par = dv.groupby("Cuenta")["Valor_Vista"].sum().sort_values(ascending=False)
        par = par[par > 0]
        if not par.empty:
            pdf = par.reset_index()
            pdf.columns = ["Cuenta", "Monto"]
            pdf["Acumulado"] = pdf["Monto"].cumsum() / pdf["Monto"].sum() * 100
            pdf = pdf.head(15)
            b = alt.Chart(pdf).encode(x=alt.X("Cuenta:N", sort=None, title=None))
            barras = b.mark_bar(color=MESS_BLUE).encode(
                y=alt.Y("Monto:Q", title=cur), tooltip=["Cuenta", alt.Tooltip("Monto:Q", format=",.0f")])
            linea = b.mark_line(color=ACCENT, point=True).encode(
                y=alt.Y("Acumulado:Q", scale=alt.Scale(domain=[0, 100]), title="% acumulado"))
            regla = alt.Chart(pd.DataFrame({"y": [80]})).mark_rule(color=RED, strokeDash=[5, 5]).encode(
                y=alt.Y("y:Q", scale=alt.Scale(domain=[0, 100])))
            show_chart(alt.layer(barras, linea + regla).resolve_scale(y="independent").properties(height=320))
        else:
            st.info("Sin montos en esta vista.")
    with g2:
        st.markdown("**Embudo: bruto frente a ponderado**")
        emb = dv.groupby("Fase").agg(Bruto=("Valor_Vista", "sum"), Ponderado=("Pond_Vista", "sum")).reset_index()
        if not emb.empty and emb["Bruto"].sum() > 0:
            ch_b = alt.Chart(emb).mark_bar(color="#9db8d6").encode(
                y=alt.Y("Fase:N", sort="ascending", title=None), x=alt.X("Bruto:Q", title=cur, stack=None),
                tooltip=["Fase", alt.Tooltip("Bruto:Q", format=",.0f")])
            ch_p = alt.Chart(emb).mark_bar(color=MESS_BLUE, size=10).encode(
                y=alt.Y("Fase:N", sort="ascending"), x=alt.X("Ponderado:Q", stack=None),
                tooltip=["Fase", alt.Tooltip("Ponderado:Q", format=",.0f")])
            show_chart(alt.layer(ch_b, ch_p).properties(height=320))
            st.caption("Barra clara: monto bruto. Barra oscura: monto ponderado.")
        else:
            st.info("Sin montos en esta vista.")

    st.markdown("**Forecast ponderado por área o marca**")
    fa = dv.groupby("Area")["Pond_Vista"].sum().sort_values(ascending=False).head(12).reset_index()
    fa = fa[fa["Pond_Vista"] > 0]
    if not fa.empty:
        show_chart(alt.Chart(fa).mark_bar(color=MESS_DARK).encode(
            y=alt.Y("Area:N", sort="-x", title=None), x=alt.X("Pond_Vista:Q", title="Ponderado " + cur),
            tooltip=["Area", alt.Tooltip("Pond_Vista:Q", format=",.0f")]).properties(height=300))

    st.markdown("### Ranking de cuentas clave")
    rk = df.groupby("Cuenta").agg(
        Proyectos=("Folio", "count"), USD=("Monto_USD", "sum"), MXN=("Monto_MXN", "sum"),
        Total=("Total_USD_Eq", "sum"), Ponderado=("Ponderado", "sum"),
        Fase_Max=("Fase_Num", "max"), Dias_max=("Dias_Registro", "max"),
        En_Rojo=("Semaforo", lambda x: int((x == "Rojo").sum())),
        Sin_Cotizar=("Sin_Cotizar", "sum"),
    ).reset_index().sort_values("Total", ascending=False).reset_index(drop=True)
    total_rk = float(rk["Total"].sum())
    if total_rk > 0:
        rk["Pct"] = rk["Total"] / total_rk * 100
        rk["Pct_Acum"] = rk["Pct"].cumsum()
        rk["Clave"] = np.where((rk["Pct_Acum"] - rk["Pct"]) < 80, "Clave 80%", "")
        n80 = int((rk["Clave"] != "").sum())
        st.caption(
            str(n80) + " de " + str(len(rk)) + " cuentas concentran el 80% del valor del pipeline filtrado. "
            "Ordenado por total equivalente en USD; el ponderado usa la probabilidad por fase."
        )
    else:
        rk["Pct"], rk["Pct_Acum"], rk["Clave"] = 0.0, 0.0, ""
    rk["Fase más avanzada"] = rk["Fase_Max"].map(FASES)
    rk.insert(0, "#", range(1, len(rk) + 1))
    rk_show = rk[["#", "Cuenta", "Proyectos", "USD", "MXN", "Total", "Pct", "Pct_Acum", "Ponderado",
                  "Fase más avanzada", "Dias_max", "En_Rojo", "Sin_Cotizar", "Clave"]].rename(columns={
        "Total": "Total Eq. USD", "Pct": "% del total", "Pct_Acum": "% acum.", "Ponderado": "Ponderado USD",
        "Dias_max": "Días reg. máx.", "En_Rojo": "En rojo", "Sin_Cotizar": "Sin cotizar",
    })
    rk_sty = rk_show.style.format({
        "USD": "${:,.2f}", "MXN": "${:,.2f}", "Total Eq. USD": "${:,.0f}", "Ponderado USD": "${:,.0f}",
        "% del total": "{:.1f}%", "% acum.": "{:.1f}%",
    })
    try:
        st.dataframe(rk_sty, hide_index=True, width="stretch")
    except TypeError:
        st.dataframe(rk_sty, hide_index=True, use_container_width=True)

    st.markdown("### Cuentas con 2 o más proyectos (candidatas a bundle)")
    cta = df.groupby("Cuenta").agg(
        Proyectos=("Folio", "count"), USD=("Monto_USD", "sum"), MXN=("Monto_MXN", "sum"),
        Total=("Total_USD_Eq", "sum"), Ponderado=("Ponderado", "sum"),
        Dias_max=("Dias_Registro", "max"),
    ).reset_index()
    cta = cta[cta["Proyectos"] >= 2].sort_values("Total", ascending=False)
    if cta.empty:
        st.info("No hay cuentas con múltiples proyectos bajo estos filtros.")
    else:
        sty = cta.rename(columns={"Total": "Total Eq. USD", "Ponderado": "Ponderado USD", "Dias_max": "Días reg. máx."}).style.format(
            {"USD": "${:,.2f}", "MXN": "${:,.2f}", "Total Eq. USD": "${:,.0f}", "Ponderado USD": "${:,.0f}"})
        try:
            st.dataframe(sty, hide_index=True, width="stretch")
        except TypeError:
            st.dataframe(sty, hide_index=True, use_container_width=True)

    st.markdown("### Detalle completo del pipeline")
    det = df.sort_values("Total_USD_Eq", ascending=False)
    cols_det = ["Folio", "Cliente", "Cuenta", "Descripcion", "Area", "Fase", "Monto_USD", "Monto_MXN",
                "Total_USD_Eq", "Ponderado", "Cotizacion", "Cierre_Est", "Dias_Registro", "Semaforo", "Alerta"]
    show_table(det, cols_det)
    totals_caption(det)
    exp = det[cols_det].rename(columns=DISPLAY)
    st.download_button("Descargar vista filtrada (CSV)", exp.to_csv(index=False).encode("utf-8-sig"),
                       file_name="pipeline_filtrado.csv", mime="text/csv")


# ---------------------------------------------------------------------------
# LABORATORIO IA
# ---------------------------------------------------------------------------
def _apply_quick():
    lab = st.session_state.get("lab_quick")
    qmap = st.session_state.get("lab_quick_map", {})
    if lab in qmap:
        cuenta, folio = qmap[lab]
        st.session_state["lab_cuenta"] = cuenta
        st.session_state["lab_folios_" + cuenta] = [folio]


def render_lab():
    st.markdown("### Laboratorio IA | Copiloto estratégico KAM")
    if base is None or df.empty:
        st.info("Sube el CSV y ajusta los filtros para trabajar una cuenta.")
        return
    st.caption("Trabaja con los proyectos que pasan los filtros activos del panel lateral.")

    top = df[df["Total_USD_Eq"] > 0].sort_values("Ponderado", ascending=False).head(10)
    qmap = {}
    for _, r in top.iterrows():
        qmap[r["Folio"] + " | " + r["Cuenta"] + " | " + fmt_usd(r["Total_USD_Eq"])] = (r["Cuenta"], r["Folio"])
    st.session_state["lab_quick_map"] = qmap
    st.selectbox("Atajo: proyecto prioritario (Top 10)", ["--"] + list(qmap.keys()), key="lab_quick", on_change=_apply_quick)

    cuentas = sorted(df["Cuenta"].unique())
    if st.session_state.get("lab_cuenta") not in ["--"] + cuentas:
        st.session_state.pop("lab_cuenta", None)
    cuenta = st.selectbox("Cuenta", ["--"] + cuentas, key="lab_cuenta")
    if cuenta == "--":
        return

    sub = df[df["Cuenta"] == cuenta].sort_values("Ponderado", ascending=False)
    etiquetas = {
        r["Folio"]: "Proj: " + r["Folio"] + " | Cot: " + (r["Cotizacion"] or "N/D") + " | " + str(r["Descripcion"])[:40] + " | " + r["Fase"] + " | $"
        + format(r["Monto_USD"], ",.0f") + " USD / $" + format(r["Monto_MXN"], ",.0f") + " MXN | "
        + str(r["Dias_Registro"]) + " d"
        for _, r in sub.iterrows()
    }
    folios = st.multiselect(
        "Folios a incluir (bundle)", list(etiquetas.keys()), default=list(etiquetas.keys())[:1],
        format_func=lambda x: etiquetas.get(x, x), key="lab_folios_" + cuenta,
    )
    if not folios:
        st.info("Selecciona al menos un folio.")
        return
    sel = sub[sub["Folio"].isin(folios)]

    usd, mxn = float(sel["Monto_USD"].sum()), float(sel["Monto_MXN"].sum())
    desglose = "\n".join([
        "• Cotización " + (r["Cotizacion"] or "sin número") + " (Proyecto " + r["Folio"] + "): " + str(r["Descripcion"])
        + " -> Inversión: $" + format(r["Monto_USD"], ",.2f") + " USD / $" + format(r["Monto_MXN"], ",.2f") + " MXN"
        for _, r in sel.iterrows()
    ])
    fase_n = int(sel["Fase_Num"].max())
    cierre_min = sel["Cierre_Est"].min()
    st.markdown(
        '<div class="kpi-card"><div class="kpi-label">Valor del paquete</div>'
        '<div class="kpi-value">$' + format(usd, ",.2f") + " USD | $" + format(mxn, ",.2f") + " MXN</div>"
        '<div class="kpi-sub">' + FASES[fase_n] + " | equivalente " + fmt_usd(sel["Total_USD_Eq"].sum())
        + " | ponderado " + fmt_usd(sel["Ponderado"].sum()) + "</div></div>",
        unsafe_allow_html=True,
    )

    obj_def = OBJETIVO_FASE.get(fase_n, OBJETIVOS[0])
    if bool(sel["Sin_Cotizar"].all()):
        obj_def = OBJETIVOS[0]
    c1, c2 = st.columns(2)
    with c1:
        objetivo = st.selectbox("Objetivo", OBJETIVOS, index=OBJETIVOS.index(obj_def) if obj_def in OBJETIVOS else 0,
                                key="obj_" + cuenta + "_" + str(fase_n))
        canal = st.radio("Canal", CANALES, horizontal=True)
        perfil = st.selectbox("Interlocutor", PERFILES)
    with c2:
        giro = st.text_input("Giro industrial", placeholder="Ej. Aeroespacial, automotriz")
        contexto = st.text_area("Contexto específico (opcional)", height=110,
                                placeholder="Ej. Pidió cotización pero hay resistencia por presupuesto o tiempos.")

    if st.button("Generar estrategia de cierre"):
        ctx = {
            "cuenta": cuenta, "folios": ", ".join(folios),
            "descripcion": " | ".join(sel["Descripcion"].astype(str))[:700],
            "usd": usd, "mxn": mxn, "fase": FASES[fase_n], "dias": int(sel["Dias_Registro"].max()),
            "cierre": cierre_min.strftime("%d/%m/%Y") if pd.notna(cierre_min) else "Sin fecha",
            "cotizaciones": ", ".join([c for c in sel["Cotizacion"].astype(str) if c]),
            "desglose": desglose,
            "objetivo": objetivo, "canal": canal, "perfil": perfil, "giro": giro, "contexto": contexto,
            "foco": FOCO_MEDDPICC.get(fase_n, FOCO_MEDDPICC[0]),
        }
        with st.spinner("Analizando la cuenta con MEDDPICC, SPIN, Sandler y ABM..."):
            txt, err = call_gemini(build_prompt(ctx))
        if err:
            st.error(err)
        else:
            tags = parse_tags(txt)
            st.session_state["ia_counter"] = st.session_state.get("ia_counter", 0) + 1
            st.session_state["ia_res"] = {
                "key": (cuenta, tuple(sorted(folios))), "ctx": ctx, "tags": tags, "raw": txt,
                "id": st.session_state["ia_counter"],
            }

    res = st.session_state.get("ia_res")
    if not res:
        return
    if res["key"] != (cuenta, tuple(sorted(folios))):
        st.info("Hay una estrategia generada para otra selección. Pulsa 'Generar estrategia de cierre' para esta.")
        return

    tags, ctx, rid = res["tags"], res["ctx"], str(res["id"])
    if not any(tags.values()):
        st.warning("La IA no devolvió las etiquetas esperadas. Se muestra la respuesta completa; vuelve a generar.")
        st.write(res["raw"])
        return
    if not tags["MESSAGE"]:
        st.warning("La respuesta no incluyó la etiqueta MESSAGE. Vuelve a generar.")

    st.divider()
    pa, pm, po, p_mkt, pl = st.tabs(["Análisis", "Mensaje", "Objeciones", "Acciones ABM / Marketing", "Log para SCOTT"])
    with pa:
        st.write(tags["ANALYSIS"])
    with pm:
        versiones = [clean_message(v) for v in re.split(r"\n\s*-{3,}\s*\n", tags["MESSAGE"]) if v.strip()]
        if len(versiones) >= 2:
            ver = st.radio("Versión", ["Breve", "Completa"], horizontal=True, key="ver_" + rid)
            base_msg = versiones[0] if ver == "Breve" else versiones[1]
        else:
            ver = "Unica"
            base_msg = clean_message(tags["MESSAGE"])
        mensaje = st.text_area("Mensaje (editable)", value=base_msg, height=190, key="msg_" + rid + "_" + ver)
    with po:
        st.write(tags["OBJECTIONS"])
    with p_mkt:
        st.write(tags.get("MARKETING", "Sin recomendaciones de marketing generadas."))
    with pl:
        log_txt = st.text_area("Registro sugerido (editable)", value=tags["LOG"], height=110, key="log_" + rid)

    st.markdown("##### Ejecución rápida")
    a1, a2 = st.columns(2)
    with a1:
        phone = st.text_input("Teléfono WhatsApp (opcional, con lada, ej. 524421234567)", key="ph_" + rid)
        st.link_button("Abrir WhatsApp con el mensaje", whatsapp_link(mensaje, phone))
    with a2:
        d1, d2 = st.columns(2)
        with d1:
            f_cita = st.date_input("Seguimiento", value=date.today() + timedelta(days=2), key="fc_" + rid)
        with d2:
            h_cita = st.time_input("Hora", value=time(10, 0), key="hc_" + rid)
        st.link_button(
            "Crear recordatorio en Google Calendar",
            gcal_link("Seguimiento " + cuenta, ctx["objetivo"] + "\n\n" + (log_txt or ""), datetime.combine(f_cita, h_cita)),
        )
    if Document is None:
        st.warning("Instala python-docx para descargar la ficha .docx.")
    else:
        try:
            st.download_button(
                "Descargar ficha estratégica (.docx)",
                data=build_docx(ctx, tags, mensaje, log_txt),
                file_name="Estrategia_" + re.sub(r"\W+", "_", cuenta) + ".docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        except Exception as e:
            st.error("No se pudo generar el .docx: " + str(e))


with tab_dash:
    try:
        render_dashboard()
    except Exception as e:
        st.error("Error en el dashboard: " + str(e))
with tab_lab:
    try:
        render_lab()
    except Exception as e:
        st.error("Error en el Laboratorio IA: " + str(e))
