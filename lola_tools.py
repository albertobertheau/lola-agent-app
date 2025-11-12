import os
import google.generativeai as genai

from drive_utils import append_to_google_doc, append_row_to_google_sheet

# Asumimos que lola_gemini_model y knowledge_base se pasarán a estas funciones
# para que no tengamos que inicializarlos aquí.

def perform_qa(user_query, lola_gemini_model, knowledge_base):
    """
    Herramienta para Q&A que primero corrige y expande la consulta, y luego usa multi-consulta.
    """
    print("🧠 Usando Herramienta: Pregunta y Respuesta (Q&A) - Modo Auto-Corrección")
    
    # --- NEW STAGE 0: QUERY CORRECTION AND EXPANSION ---
    correction_prompt = f"""
    Analiza la siguiente 'Pregunta Original del Usuario'. Tu tarea es reescribirla para que sea una consulta de búsqueda más efectiva.
    Corrige cualquier error ortográfico. Expande los términos a sus conceptos clave.
    Por ejemplo, si el usuario escribe 'info del modelo freemiun', una buena reescritura sería 'modelo de negocio freemium precios características'.

    Pregunta Original del Usuario: "{user_query}"

    Consulta Mejorada:
    """
    try:
        response = lola_gemini_model.generate_content(correction_prompt)
        corrected_query = response.text.strip()
        print(f"✅ Consulta original corregida y mejorada a: '{corrected_query}'")
    except Exception as e:
        print(f"Advertencia: Falló la corrección de la consulta. Usando la consulta original. Error: {e}")
        corrected_query = user_query # Fallback to the original query
    # --- END OF NEW STAGE ---

    # --- STAGE 1: KEYWORD GENERATION (Now uses the corrected query) ---
    keyword_generation_prompt = f"""
    Dada la siguiente consulta de búsqueda, genera 3 consultas alternativas y concisas.
    Consulta de búsqueda: "{corrected_query}"
    Consultas alternativas:
    """
    try:
        response = lola_gemini_model.generate_content(keyword_generation_prompt)
        alternative_queries = response.text.strip().split(';')
    except Exception as e:
        print(f"Advertencia: Falló la generación de consultas alternativas. Usando solo la consulta mejorada. Error: {e}")
        alternative_queries = []

    # Combine the corrected query with the generated ones
    all_queries = [corrected_query] + alternative_queries
    print(f"🔍 Ejecutando búsquedas para las consultas: {all_queries}")
    
    # --- STAGE 2: MULTI-QUERY RETRIEVAL ---
    all_retrieved_chunks = []
    retrieved_ids = set()
    for query in all_queries:
        if not query: continue
        results = knowledge_base.query(query, n_results=3)
        if results and results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                chunk_id = results['ids'][0][i]
                if chunk_id not in retrieved_ids:
                    all_retrieved_chunks.append(results['documents'][0][i])
                    retrieved_ids.add(chunk_id)

    if not all_retrieved_chunks:
        return "No tengo esa información específica en mis documentos."

    # --- STAGE 3: SYNTHESIS (The same strict but synthesizing prompt) ---
    persona_prompt = (
        "Eres un asistente de IA experto llamado Lola. Tu tarea es responder la 'Pregunta del Usuario Original' basándote únicamente en la información contenida en el 'Contexto del Documento'.\n"
        "REGLAS IMPORTANTES:\n"
        "1. Tu respuesta DEBE derivarse exclusivamente del 'Contexto del Documento'.\n"
        "2. Sintetiza la información para construir una respuesta completa y coherente.\n"
        "3. Si la respuesta no se puede construir, responde de forma clara y directa: 'No tengo esa información específica en mis documentos.'"
    )
    
    context_prompt = "\n\n**Contexto del Documento:**\n---\n" + "\n---\n".join(all_retrieved_chunks) + "\n---\n"
    # Note: We use the *original* user_query here for the final answer, which feels more natural.
    full_prompt = f"{persona_prompt}\n\n**Pregunta del Usuario Original:** {user_query}\n\n**Respuesta de Lola:**"
    
    final_response = lola_gemini_model.generate_content(full_prompt)
    return final_response.text

def perform_content_generation(user_query, lola_gemini_model, knowledge_base):
    """Herramienta para generar contenido creativo (emails, tweets, etc.) basado en los documentos."""
    print("✍️ Usando Herramienta: Generador de Contenido")

    persona_prompt = (
        "Eres Lola, una experta en comunicación y marketing para ChainBrief. Tu tarea es generar contenido nuevo (como emails, posts para redes sociales, resúmenes) "
        "basándote en la 'Información Relevante' extraída de los documentos internos. Adopta el tono y estilo de ChainBrief. "
        "REGLA CRÍTICA: Debes fundamentar cada pieza de contenido en los hechos proporcionados. No inventes métricas, fechas o características."
    )
    
    # Lógica RAG (idéntica, para obtener el contexto)
    results = knowledge_base.query(user_query, n_results=7) # Podemos tomar más contexto para creatividad
    retrieved_content = []
    if results and results['documents'] and results['documents'][0]:
        retrieved_content = results['documents'][0]

    context_prompt = "\n\n**Información Relevante de Documentos Internos:**\n" + "\n---\n".join(retrieved_content)
    full_prompt = f"{persona_prompt}{context_prompt}\n\n**Petición del Usuario:** {user_query}\n\n**Contenido Generado por Lola:**"
    
    response = lola_gemini_model.generate_content(full_prompt)
    return response.text

def perform_strategic_analysis(user_query, lola_gemini_model, knowledge_base):
    """Herramienta para dar recomendaciones y análisis, citando sus fuentes."""
    print("📈 Usando Herramienta: Analista Estratégico")

    persona_prompt = (
        "Eres Lola, una analista de negocios y estratega para ChainBrief. Tu tarea es analizar la 'Información Relevante' para responder preguntas complejas, "
        "identificar riesgos, oportunidades y dar recomendaciones. "
        "REGLA CRÍTICA: Debes pensar paso a paso. Tu respuesta debe ser estructurada y siempre debes citar el documento o la idea de la 'Información Relevante' que respalda cada punto de tu análisis. "
        "Por ejemplo: 'Basado en el One-Pager, una oportunidad es...' o 'El Pitch Deck menciona un riesgo sobre...'"
    )
    
    # Lógica RAG (idéntica, para obtener el contexto)
    results = knowledge_base.query(user_query, n_results=10) # Tomamos mucho contexto para un buen análisis
    retrieved_content = []
    if results and results['documents'] and results['documents'][0]:
        retrieved_content = results['documents'][0]

    context_prompt = "\n\n**Información Relevante de la Base de Conocimiento:**\n" + "\n---\n".join(retrieved_content)
    full_prompt = f"{persona_prompt}{context_prompt}\n\n**Solicitud de Análisis del Usuario:** {user_query}\n\n**Análisis de Lola:**"
    
    response = lola_gemini_model.generate_content(full_prompt)
    return response.text

def perform_document_writing(user_query, lola_gemini_model, drive_service):
    """Herramienta para interpretar una orden y escribir en un Google Doc o Sheet."""
    print("✍️ Usando Herramienta: Escritor de Documentos")

    # Obtenemos las IDs de los documentos desde las variables de entorno
    qna_doc_id = os.getenv("QNA_DOC_ID")
    itinerary_sheet_id = os.getenv("ITINERARY_SHEET_ID")

    writing_prompt = f"""
    Tu tarea es actuar como un asistente de escritura. Analiza la petición del usuario y extráela en un formato JSON estructurado.
    La petición especificará un documento de destino y el contenido a escribir.

    Los posibles documentos de destino son:
    - "qna_document": Si el usuario menciona "Q&A", "preguntas y respuestas", o un formato similar.
    - "itinerary_sheet": Si el usuario menciona "itinerario", "agenda", "calendario" o un evento.

    El contenido a escribir debe ser extraído literalmente de la petición.
    - Para "qna_document", el contenido debe ser el texto completo a añadir.
    - Para "itinerary_sheet", el contenido debe ser una lista de strings representando las columnas (ej: ["Fecha", "Hora", "Evento"]).

    Petición del usuario: "{user_query}"

    Responde únicamente con un objeto JSON con las claves "target_document" y "content_to_write".
    Ejemplo para Q&A: {{"target_document": "qna_document", "content_to_write": "P: ¿Cuál es nuestro inversor principal?\\nR: Aún no tenemos uno."}}
    Ejemplo para Itinerario: {{"target_document": "itinerary_sheet", "content_to_write": ["2025-11-20", "3:00 PM", "Reunión con inversores"]}}
    """

    try:
        response = lola_gemini_model.generate_content(writing_prompt)
        # Limpiamos la respuesta para obtener solo el JSON
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        
        import json
        action = json.loads(json_response_text)
        
        target = action.get("target_document")
        content = action.get("content_to_write")

        if target == "qna_document":
            if append_to_google_doc(drive_service, qna_doc_id, content):
                return "Entendido. He actualizado el documento de Preguntas y Respuestas."
        elif target == "itinerary_sheet":
            if append_row_to_google_sheet(drive_service, itinerary_sheet_id, content):
                return "De acuerdo. He añadido la entrada al Itinerario del Proyecto."
        
        return "No pude determinar el documento de destino o el contenido a escribir. Por favor, sé más específico."

    except Exception as e:
        print(f"❌ Error en la herramienta de escritura: {e}")
        return "Lo siento, tuve un problema al interpretar tu instrucción de escritura. Inténtalo de nuevo."