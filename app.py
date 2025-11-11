import streamlit as st
from lola_main_agent import LolaAgent
# We need to import the specific writing tool function to call it directly
from lola_tools import perform_document_writing

# --- Page Configuration ---
st.set_page_config(
    page_title="Lola Agent - ChainBrief Expert",
    page_icon="🧠",
    layout="wide"
)

# --- Agent Initialization ---
@st.cache_resource
def load_lola_agent():
    print("Iniciando Lola Agent por primera vez para la sesión de Streamlit...")
    agent = LolaAgent()
    agent.populate_knowledge_base()
    print("Base de conocimiento poblada. Lola está lista.")
    return agent

lola = load_lola_agent()


# --- Sidebar for Actions ---
with st.sidebar:
    st.header("Acciones del Agente")
    st.markdown("Usa este botón para forzar una sincronización con Google Drive.")
    
    if st.button("🔄 Sincronizar Base de Conocimiento"):
        with st.spinner("Buscando nuevos documentos y actualizaciones..."):
            lola.check_for_updates()
        st.success("¡Sincronización completada!")
        st.balloons()
    
    st.divider()

    # --- NEW: DOCUMENT WRITING TOOL ---
    st.header("Herramienta de Escritura")
    st.markdown(
        "Escribe una instrucción para añadir información a un documento. \n"
        "Ej: `Añade al Q&A: P: Cuál es el objetivo? R: Ser líderes.` \n"
        "Ej: `Registra en el itinerario: 2025-12-05, 11 AM, Demo con Inversores`"
    )
    
    writing_instruction = st.text_area("Instrucción de escritura:", height=100)
    
    if st.button("📝 Ejecutar Escritura"):
        if writing_instruction:
            with st.spinner("Interpretando y ejecutando la instrucción..."):
                # We call the writing tool directly, passing the necessary components
                response = perform_document_writing(
                    user_query=writing_instruction,
                    lola_gemini_model=lola.lola_gemini_model, # Pass the model from the agent
                    drive_service=lola.drive_service         # Pass the drive service from the agent
                )
            st.success(response) # Display the confirmation message from the tool
        else:
            st.warning("Por favor, escribe una instrucción antes de ejecutar.")
    # --- END OF NEW TOOL ---


# --- Main Chat Interface ---
st.title("🤖 Lola Agent: Your ChainBrief Expert")
st.caption("Hazme una pregunta, pídeme que genere contenido o que analice nuestros documentos.")

# Chat History Management
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "¡Hola! Estoy lista para ayudarte. ¿Qué necesitas?"}]

# Display existing messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input and Response Logic
if prompt := st.chat_input("¿Qué te gustaría saber?"):
    # Add user's message to history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get and display Lola's response
    with st.chat_message("assistant"):
        with st.spinner("Lola está pensando..."):
            
            # --- NEW: ROBUST ERROR HANDLING FOR THE UI ---
            try:
                # The regular chat input still uses the main answer_query router
                response = lola.answer_query(prompt)
            except Exception as e:
                if "429" in str(e) and "quota" in str(e).lower():
                    print(f"❌ Límite de tasa de Gemini alcanzado en la app. Error: {e}")
                    response = "He recibido demasiadas peticiones en este momento. Por favor, espera un minuto antes de volver a preguntar."
                else:
                    print(f"❌ Error inesperado en la app: {e}")
                    response = "Lo siento, tuve un problema inesperado al procesar tu petición."
            # --- END OF NEW ERROR HANDLING ---

        st.markdown(response)
    
    # Add Lola's response to history
    st.session_state.messages.append({"role": "assistant", "content": response})