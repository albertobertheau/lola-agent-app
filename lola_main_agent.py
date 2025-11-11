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
from lola_tools import perform_qa, perform_content_generation, perform_strategic_analysis, perform_document_writing

import streamlit as st

load_dotenv()

# Configure Gemini with a new method that works both locally and deployed
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except (KeyError, AttributeError):
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
        self.lola_gemini_model = lola_gemini_model 
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
                self.knowledge_base.add_document(doc_id=chunk_data['id'], content=chunk_data['content'], metadata=chunk_data['metadata'])
        print("Knowledge base population complete.")
        self.last_update_check_time = datetime.now()

    def route_query(self, user_query):
        """Usa el LLM para clasificar la intención del usuario y elegir una herramienta."""
        print(f"🚦 Enrutando la petición: '{user_query}'")
        
        routing_prompt = f"""
        Dada la siguiente petición de un usuario, clasifícala en una de las siguientes cuatro categorías:
        1.  "qa": Si es una pregunta directa sobre hechos. Ej: "¿Quién es el CEO?".
        2.  "generation": Si pide crear contenido nuevo. Ej: "Redacta un email".
        3.  "analysis": Si pide una opinión, recomendación o análisis. Ej: "¿Cuáles son nuestros riesgos?".
        4.  "writing": Si es una orden para añadir, actualizar, escribir o registrar información en un documento. Ej: "Añade esto al Q&A", "Actualiza el itinerario con esta reunión".

        Petición del usuario: "{user_query}"

        Responde únicamente con una de las cuatro categorías en minúsculas.
        """
        
        response = lola_gemini_model.generate_content(routing_prompt)
        tool_name = response.text.strip().lower()
        
        if tool_name not in ["qa", "generation", "analysis", "writing"]:
            return "qa"
        
        return tool_name

    def answer_query(self, user_query):
        """Responde a una consulta del usuario usando el enrutador de tareas."""
        if not lola_gemini_model:
            return "Lo siento, mi modelo no está inicializado."
            
        chosen_tool = self.route_query(user_query)
        
        try:
            if chosen_tool == "generation":
                return perform_content_generation(user_query, lola_gemini_model, self.knowledge_base)
            elif chosen_tool == "analysis":
                return perform_strategic_analysis(user_query, lola_gemini_model, self.knowledge_base)
            elif chosen_tool == "writing":
                # La herramienta de escritura necesita el 'drive_service' en lugar de la 'knowledge_base'
                return perform_document_writing(user_query, lola_gemini_model, self.drive_service)
            else: # "qa" es el default
                return perform_qa(user_query, lola_gemini_model, self.knowledge_base)
        except Exception as e:
            if "429" in str(e) and "quota" in str(e).lower():
                print(f"❌ Límite de tasa de Gemini alcanzado. Error: {e}")
                return "He recibido demasiadas peticiones en este momento. Por favor, espera un minuto antes de volver a preguntar."
            else:
                print(f"❌ Error ejecutando la herramienta: {e}")
                return "Lo siento, tuve un problema inesperado al procesar tu petición."

    def check_for_updates(self):
        """Periodically checks Google Drive for new or modified files and updates the KB."""
        print("\n--- [SCHEDULER] Realizando verificación periódica de actualizaciones en Drive ---")
        current_time = datetime.now()
        query_time_str = self.last_update_check_time.isoformat("T") + "Z"
        updated_files = list_all_files_in_folder_recursive(self.drive_service, self.chainbrief_root_folder_id, query_conditions=f"modifiedTime > '{query_time_str}'")
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
            
            # --- NEW: CHECK FOR EMPTY INPUT ---
            if not user_input.strip(): # If the input is empty or just spaces
                continue # Skip the rest of the loop and ask again
            # --- END OF NEW CHECK ---

            if user_input.lower() == 'salir': 
                break

            query_lower = user_input.lower()
            if 'actualiza' in query_lower or 'update' in query_lower or 'sincroniza' in query_lower or 'sync' in query_lower:
                print("\nLola: Entendido. Iniciando una sincronización manual con Google Drive...")
                lola.check_for_updates()
                print("\nLola: ¡Sincronización completada! Ya tengo la información más reciente.")
                continue
            
            response = lola.answer_query(user_input)
            print(f"\nLola: {response}")
            
    finally:
        print("\nApagando Lola Agent...")
        scheduler.shutdown()
        print("Lola Agent apagada.")