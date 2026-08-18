# 5. Procesamiento de Datos (A prueba de errores)
if archivo_cargado is not None:
    df = pd.read_csv(archivo_cargado)
    
    # Esto nos ayuda a ver qué nombres tiene realmente tu archivo
    columnas_reales = df.columns.tolist()
    
    columnas_oro = ["Cotización", "Cliente", "Parque_Industrial", "Monto_MXN", "Dias_Sin_Contacto", "Temperatura"]
    
    # Verificamos si faltan columnas
    faltantes = [c for c in columnas_oro if c not in df.columns]
    
    if faltantes:
        st.error(f"⚠️ El sistema no encuentra estas columnas exactas: {faltantes}")
        st.write("Columnas detectadas en tu archivo:", columnas_reales)
        st.stop()
    else:
        df = df[columnas_oro]
        df['Estatus_SLA'] = df['Dias_Sin_Contacto'].apply(calcular_semaforo)
else:
    df = cargar_datos_demo()
