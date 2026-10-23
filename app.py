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
