import os
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

# Import your custom modules
from drive_utils import get_drive_service, list_all_files_in_folder_recursive, download_file
from doc_processor import read_text_from_file, chunk_text
from knowledge_base import KnowledgeBase
from gemini_agent import summarize_text_with_gemini

import streamlit as st # Don't forget to add this to your imports at the top!

load_dotenv()

# Configure Gemini with a new method that works both locally and deployed
try:
    # Try to get the key from Streamlit's secrets manager (for deployment)
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, AttributeError):
    # Fall back to the .env file if secrets aren't available (for local development)
    print("Secrets not found on Streamlit, falling back to .env file for local development.")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY no se encontró ni en los secrets de Streamlit ni en el archivo .env.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    LOLA_LLM_MODEL_NAME = 'models/gemini-pro-latest'
    lola_gemini_model = genai.GenerativeModel(LOLA_LLM_MODEL_NAME)
    print(f"✅ Lola's main Gemini model configurado usando '{LOLA_LLM_MODEL_NAME}'.")
except Exception as e:
    print(f"❌ Error configurando Lola's main Gemini model: {e}")
    lola_gemini_model = None

class LolaAgent:
    def __init__(self, kb_collection_name="chainbrief_docs", temp_dir="temp_docs"):
        self.drive_service = get_drive_service()
        self.knowledge_base = KnowledgeBase(collection_name=kb_collection_name)
        self.temp_dir = temp_dir
        os.makedirs(self.temp_dir, exist_ok=True)
        print("Lola Agent initialized.")

        self.last_update_check_time = datetime.min 
        self.chainbrief_root_folder_id = os.getenv("CHAINBRIEF_ROOT_FOLDER_ID") 

        if not self.chainbrief_root_folder_id:
            print("⚠️ ADVERTENCIA: CHAINBRIEF_ROOT_FOLDER_ID no configurado en .env.")

        print("Limpiando y recreando ChromaDB para reindexación...")
        try:
            self.knowledge_base.client.delete_collection(name=kb_collection_name)
            self.knowledge_base = KnowledgeBase(collection_name=kb_collection_name)
            print("✅ ChromaDB reiniciada con éxito.")
        except Exception as e:
            print(f"⚠️ Error al limpiar ChromaDB (puede que no existiera): {e}")

    def _get_document_content(self, file_id, file_name, mime_type):
        """Downloads and extracts text from a file."""
        local_path = download_file(self.drive_service, file_id, file_name, self.temp_dir)
        if local_path:
            content = read_text_from_file(local_path, mime_type=mime_type)
            try:
                os.remove(local_path)
            except OSError as e:
                print(f"Error removing temporary file {local_path}: {e}")
            return content
        return None

    def populate_knowledge_base(self):
        """Initial population of the knowledge base from Google Drive."""
        if not self.knowledge_base.is_functional: return
        if not self.chainbrief_root_folder_id: return
        
        print("--- Fase 1: Recopilando y procesando todos los documentos de Drive ---")
        
        all_chunks_to_add = [] 
        
        files = list_all_files_in_folder_recursive(self.drive_service, self.chainbrief_root_folder_id)
        print(f"Se encontraron {len(files)} archivos para procesar en Drive...")

        for file in files:
            file_id, file_name, mime_type = file['id'], file['name'], file['mimeType']
            
            if mime_type == 'application/json' or file_name.lower().endswith('.json'):
                print(f"Ignorando archivo de configuración: {file_name}")
                continue
            
            print(f"Procesando: {file_name}")
            content = self._get_document_content(file_id, file_name, mime_type)
            
            if content:
                chunks = chunk_text(content, chunk_size=1000, chunk_overlap=100)
                for i, chunk_content in enumerate(chunks):
                    chunk_id = f"{file_id}-{i}"
                    metadata = { "file_id": file_id, "file_name": file_name, "mime_type": mime_type }
                    all_chunks_to_add.append({'id': chunk_id, 'content': chunk_content, 'metadata': metadata})
            else:
                print(f"No se pudo extraer el contenido de {file_name}.")
        
        print(f"\n--- Fase 2: Añadiendo {len(all_chunks_to_add)} fragmentos a la base de datos ---")
        
        if all_chunks_to_add:
            for chunk_data in all_chunks_to_add:
                self.knowledge_base.add_document(
                    doc_id=chunk_data['id'],
                    content=chunk_data['content'],
                    metadata=chunk_data['metadata']
                )

        print("Knowledge base population complete.")
        self.last_update_check_time = datetime.now()

    def answer_query(self, user_query):
        """Answers a user query using a more flexible tool router and RAG."""
        if not lola_gemini_model:
            return "Lo siento, mi modelo de lenguaje no está inicializado. No puedo responder."

        print(f"\nUsuario: {user_query}")
        
        # --- NEW & IMPROVED: FLEXIBLE TOOL ROUTER ---
        # Normalize the query to lowercase and without accents for better matching
        import unicodedata
        def normalize_text(text):
            return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()

        normalized_query = normalize_text(user_query)

        # Tool 1: Count Documents (now checks for multiple keywords)
        if ('cuantos' in normalized_query and 'documentos' in normalized_query) or 'how many documents' in normalized_query:
            doc_count = self.knowledge_base.count_documents()
            return f"Actualmente tengo {doc_count} fragmentos de texto indexados en mi base de conocimiento."

        # Tool 2: List All Documents (now checks for multiple keywords)
        if ('lista' in normalized_query and 'documentos' in normalized_query) or 'list of documents' in normalized_query:
            doc_names = self.knowledge_base.get_all_document_names()
            if doc_names:
                doc_list_formatted = "\n".join([f"- {name}" for name in doc_names])
                return f"Claro, aquí tienes la lista de los documentos que tengo en mi base de conocimiento:\n{doc_list_formatted}"
            else:
                return "No encontré ningún documento en mi base de conocimiento en este momento."
        
        # --- END OF TOOL ROUTER ---


        # --- Default Action: RAG Process for knowledge questions ---
        persona_prompt = (
            "Eres un asistente de IA llamado Lola, un experto en los documentos internos de ChainBrief. "
            "Tu tarea es responder preguntas basándote **única y exclusivamente** en la información proporcionada en la sección 'Información Relevante'. "
            "**REGLA CRÍTICA:** No debes añadir, inferir, o suponer ninguna información que no esté explícitamente escrita en el texto proporcionado. "
            "Si la respuesta a la pregunta no se encuentra en la 'Información Relevante', debes responder **exactamente** con la frase: "
            "'No tengo esa información específica en mis documentos.'"
        )
        retrieved_content, retrieved_file_names = [], set()
        if self.knowledge_base.is_functional:
            results = self.knowledge_base.query(user_query, n_results=5)
            if results and results['documents'] and results['documents'][0]:
                for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                    retrieved_content.append(doc)
                    retrieved_file_names.add(meta.get('file_name', 'Desconocido'))
                print(f"✅ Contexto recuperado de: {', '.join(sorted(list(retrieved_file_names)))}")
            else:
                print("🔍 No se encontraron documentos relevantes en la base de conocimiento.")
        else:
            print("❌ Base de conocimiento no funcional. La consulta RAG no se ejecutará.")

        # This line is now correct
        context_prompt = ""
        if retrieved_content:
            context_prompt = "\n\n**Información Relevante:**\n" + "\n---\n".join(retrieved_content)
        
        full_prompt = f"{persona_prompt}{context_prompt}\n\n**Consulta del Usuario:** {user_query}\n\n**Respuesta de Lola:**"
        
        try:
            response = lola_gemini_model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Lo siento, tuve un error al procesar tu consulta con Gemini Pro: {e}"

    # --- NEW: IMPLEMENTED CHECK_FOR_UPDATES FUNCTION ---
    def check_for_updates(self):
        """Periodically checks Google Drive for new or modified files and updates the KB."""
        print("\n--- [SCHEDULER] Realizando verificación periódica de actualizaciones en Drive ---")
        current_time = datetime.now()
        
        query_time_str = self.last_update_check_time.isoformat("T") + "Z"
        
        updated_files = list_all_files_in_folder_recursive(
            self.drive_service,
            self.chainbrief_root_folder_id,
            query_conditions=f"modifiedTime > '{query_time_str}'"
        )

        if not updated_files:
            print("[SCHEDULER] No se encontraron nuevas actualizaciones.")
        else:
            print(f"✅ [SCHEDULER] Se encontraron {len(updated_files)} archivos actualizados.")
            for file in updated_files:
                file_id, file_name, mime_type = file['id'], file['name'], file['mimeType']
                
                try:
                    self.knowledge_base.collection.delete(where={"file_id": file_id})
                    print(f"[SCHEDULER] Eliminados los fragmentos antiguos del archivo: {file_name}")
                except Exception as e:
                    print(f"Advertencia: No se pudieron eliminar los fragmentos antiguos (puede que no existieran): {e}")

                print(f"[SCHEDULER] Procesando archivo actualizado: {file_name}")
                content = self._get_document_content(file_id, file_name, mime_type)
                if content:
                    chunks = chunk_text(content, chunk_size=1000, chunk_overlap=100)
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"{file_id}-{i}"
                        metadata = { "file_id": file_id, "file_name": file_name, "mime_type": mime_type }
                        self.knowledge_base.add_document(chunk_id, chunk, metadata)
        
        self.last_update_check_time = current_time
        print("--- [SCHEDULER] Verificación de actualizaciones finalizada. ---")
    # --- END OF NEW FUNCTION ---

# --- UPDATED: MAIN EXECUTION BLOCK WITH SCHEDULER ---
if __name__ == '__main__':
    print("Iniciando Lola Agent...")
    lola = LolaAgent()
    print("\nIniciando población inicial...")
    lola.populate_knowledge_base()
    print("Población inicial completada.")
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(lola.check_for_updates, 'interval', minutes=30, id="drive_update_check")
    scheduler.start()
    print("Lola Agent running with scheduled tasks. Type 'salir' to exit.")
    print("\nLola está lista. Haz tus preguntas sobre ChainBrief.")
    
    try:
        while True:
            user_input = input("\nTu pregunta: ")
            if user_input.lower() == 'salir': 
                break

            # --- NEW: MANUAL UPDATE TRIGGER ---
            query_lower = user_input.lower()
            if 'actualiza' in query_lower or 'update' in query_lower or 'sincroniza' in query_lower or 'sync' in query_lower:
                print("\nLola: Entendido. Iniciando una sincronización manual con Google Drive...")
                lola.check_for_updates()
                print("\nLola: ¡Sincronización completada! Ya tengo la información más reciente.")
                continue # Skip the answer_query part and ask for the next question
            # --- END OF NEW TRIGGER ---

            # If it's not an update command, proceed as normal
            response = lola.answer_query(user_input)
            print(f"\nLola: {response}")
            
    finally:
        print("\nApagando Lola Agent...")
        scheduler.shutdown()
        print("Lola Agent apagada.")