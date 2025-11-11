import os
import google.generativeai as genai

from drive_utils import append_to_google_doc, append_row_to_google_sheet

# Asumimos que lola_gemini_model y knowledge_base se pasarán a estas funciones
# para que no tengamos que inicializarlos aquí.

def perform_qa(user_query, lola_gemini_model, knowledge_base):
    """
    Herramienta para Preguntas y Respuestas directas.
    Es estricta para no usar conocimiento externo, pero puede sintetizar respuestas.
    """
    print("🧠 Usando Herramienta: Pregunta y Respuesta (Q&A) - Modo Balanceado")
    
    # --- THIS IS THE NEW, BALANCED PROMPT ---
    persona_prompt = (
        "Eres un asistente de IA experto llamado Lola. Tu tarea es responder la 'Pregunta del Usuario' basándote únicamente en la información contenida en el 'Contexto del Documento'.\n"
        "REGLAS IMPORTANTES:\n"
        "1. Tu respuesta DEBE derivarse exclusivamente del 'Contexto del Documento'. No utilices conocimiento externo.\n"
        "2. Puedes sintetizar y combinar información de diferentes partes del contexto para construir una respuesta completa y coherente.\n"
        "3. Si, después de analizar todo el contexto, la respuesta a la pregunta no se puede construir, responde de forma clara y directa: 'No tengo esa información específica en mis documentos.' No inventes ni supongas nada."
    )
    
    # RAG Logic (The same as before)
    results = knowledge_base.query(user_query, n_results=5)
    retrieved_content = []
    if results and results['documents'] and results['documents'][0]:
        retrieved_content = results['documents'][0]
    
    context_prompt = "\n\n**Contexto del Documento:**\n---\n" + "\n---\n".join(retrieved_content) + "\n---\n"
    full_prompt = f"{persona_prompt}\n\n**Pregunta del Usuario:** {user_query}\n\n**Respuesta de Lola:**"
    
    response = lola_gemini_model.generate_content(full_prompt)
    return response.text

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