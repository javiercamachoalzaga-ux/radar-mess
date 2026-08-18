if archivo_cargado is not None:
    # Agregamos encoding='latin-1' para que pueda leer caracteres latinos sin error
    df = pd.read_csv(archivo_cargado, encoding='latin-1').dropna(subset=['COTIZACION', 'CLIENTE'])
    df.columns = df.columns.str.strip()
    
    # Traductor actualizado
    traductor = {
        "COTIZACION": "Cotización", 
        "CLIENTE": "Cliente", 
        "VALOR": "Monto_Bruto"
    }
    df = df.rename(columns=traductor)
    
    # LIMPIEZA
    def limpiar_monto(x):
        try:
            return float(''.join(c for c in str(x) if c.isdigit() or c == '.'))
        except: return 0.0

    df['Monto_MXN'] = df['Monto_Bruto'].apply(limpiar_monto)
    
    st.subheader("📊 Visión Financiera")
    st.metric("Total Cotizado", f"${df['Monto_MXN'].sum():,.2f} MXN")
    st.data_editor(df[['Cotización', 'Cliente', 'Monto_MXN']], hide_index=True)
