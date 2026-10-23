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
# Probabilidad inicial por fase: calíbrala con tu histórico real de cierre.
PROB_DEFAULT = {1: 10, 2: 25, 3: 50, 4: 80}
# Antigüedad (días desde el registro) esperada como máximo por fase.
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
DIAS_FRESCO = 25  # umbral de tu versión en GitHub: en tiempo (menos de 25 días) frente a rezagado
CANALES = ["WhatsApp", "Correo ejecutivo", "Llamada", "Visita presencial"]
PERFILES = ["Ingeniero de planta o calidad", "Comprador", "Director o dueño"]

# Cuentas que son el mismo grupo bajo distintos nombres en SCOTT.
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
        return None,
