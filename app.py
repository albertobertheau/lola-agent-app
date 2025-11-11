import streamlit as st
from lola_main_agent import LolaAgent # Import your existing agent class

# --- Page Configuration ---
st.set_page_config(
    page_title="Lola Agent - ChainBrief Expert",
    page_icon="🧠",
    layout="wide"
)

# --- Agent Initialization ---
# Use Streamlit's cache to load the agent only once.
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
    st.markdown("Usa este botón para forzar una sincronización con los documentos más recientes en Google Drive.")
    
    # --- NEW: MANUAL REFRESH BUTTON ---
    if st.button("🔄 Sincronizar con Google Drive"):
        with st.spinner("Buscando nuevos documentos y actualizaciones..."):
            lola.check_for_updates()
        st.success("¡Sincronización completada!")
        st.balloons()
    # --- END OF NEW BUTTON ---
    
    st.divider()
    st.info("La sincronización automática se ejecuta cada 30 minutos.")


# --- Main Chat Interface ---
st.title("🤖 Lola Agent: Your ChainBrief Expert")
st.caption("Ask me anything about our internal documents. I'll find the answer for you.")

# Chat History Management
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "¡Hola! Estoy lista para responder tus preguntas sobre ChainBrief."}]

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
            response = lola.answer_query(prompt)
        st.markdown(response)
    
    # Add Lola's response to history
    st.session_state.messages.append({"role": "assistant", "content": response})