import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# 1. Configuración de la página
st.set_page_config(page_title="Analista de Excel", layout="wide")
st.title("📊 Analista Inteligente Multiformato")
st.markdown("Sube cualquier archivo Excel. El sistema detectará las columnas y procesará los números automáticamente.")

# 2. Configuración de la API
API_KEY = st.secrets["gemini_api_key"]
genai.configure(api_key=API_KEY)

@st.cache_resource
def cargar_modelo():
    try:
        return genai.GenerativeModel(
            model_name='models/gemini-3-flash-preview',
            tools="code_execution"
        )
    except Exception as e:
        st.error(f"Error al conectar con Gemini: {e}")
        return None

model = cargar_modelo()

# 3. Función de limpieza universal de números
def limpiar_columna_numerica(serie):
    """Convierte texto con comas decimales y símbolos a números reales de Python"""
    s = serie.astype(str).str.strip()
    s = s.str.replace(r'[€\$%\s]', '', regex=True)
    s = s.str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce')

# 4. Aviso de limitaciones y botón de reset en la barra lateral
with st.sidebar:
    st.markdown("### ⚠️ Limitaciones del sistema")
    st.markdown(
        """
| Característica | Límite |
|---|---|
| Filas | 1.000 – 2.000 |
| Columnas | 10 – 20 |
| Tamaño de archivo | < 5 MB |
        """
    )
    st.divider()
    if st.button("🔄 Cerrar sesión y cargar otro Excel", use_container_width=True):
        # Limpiar estado completo de la sesión
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    uploaded_file = st.file_uploader("Sube cualquier archivo Excel", type=["xlsx", "xls"])

if uploaded_file and model:
    df_original = pd.read_excel(uploaded_file)
    df_procesado = df_original.copy()

    for col in df_procesado.columns:
        sample = str(df_procesado[col].iloc[0]) if len(df_procesado) > 0 else ""
        if any(keyword in col.lower() for keyword in ['importe', 'total', 'cuantía', 'precio', 'concesión', 'suma']):
            df_procesado[col] = limpiar_columna_numerica(df_procesado[col])
        elif re.search(r'\d+,\d+', sample):
            df_procesado[col] = limpiar_columna_numerica(df_procesado[col])

    st.sidebar.success(f"✅ {len(df_procesado)} filas cargadas")

    # CAMBIO 3: Se eliminó el bloque que mostraba el total de Importe sin solicitarlo

    # 5. Historial de chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 6. Interacción con el usuario
    if prompt := st.chat_input("Pregunta sobre tus datos (ej: ¿Cuál es el total del importe?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizando y calculando..."):
                try:
                    contexto_csv = df_procesado.to_csv(index=False)

                    instrucciones = f"""
                    Actúa como un analista de datos Senior.
                    He pre-procesado los datos para que los decimales usen el PUNTO (.) como separador,
                    asegurando que Python pueda operar con ellos correctamente.

                    DATOS DISPONIBLES:
                    {contexto_csv}

                    PREGUNTA DEL USUARIO:
                    {prompt}

                    REGLAS CRÍTICAS:
                    1. Si el usuario pide cálculos (sumas, promedios), usa la herramienta 'code_execution'.
                    2. No menciones que has usado Python, da la respuesta directa y clara.
                    3. Si el usuario pide una gráfica o tabla, genera una respuesta visual en Markdown.
                    4. Los importes finales dales formato con '€' y dos decimales.
                    5. IMPORTANTE: No incluyas bloques de código, fragmentos de Python, ni resultados
                       de ejecución en tu respuesta. Muestra únicamente el resultado final en lenguaje natural.
                    """

                    response = model.generate_content(instrucciones)

                    # CAMBIO 1: Limpieza robusta del código técnico en la respuesta
                    texto_final = response.text

                    # Eliminar bloques de código Python, output de ejecución y resultados técnicos
                    texto_final = re.sub(r'```python[\s\S]*?```', '', texto_final)
                    texto_final = re.sub(r'```[\s\S]*?```', '', texto_final)
                    # Eliminar líneas de output de ejecución de código (patrón de Gemini)
                    texto_final = re.sub(r'<output>[\s\S]*?</output>', '', texto_final)
                    texto_final = re.sub(r'\[Código ejecutado:[\s\S]*?\]', '', texto_final)
                    texto_final = texto_final.strip()

                    st.markdown(texto_final)
                    st.session_state.messages.append({"role": "assistant", "content": texto_final})

                except Exception as e:
                    st.error(f"Hubo un problema al procesar la consulta: {e}")

elif not uploaded_file:
    st.info("👋 Sube tu archivo Excel para comenzar el análisis dinámico.")
