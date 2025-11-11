import google.generativeai as genai

# Asumimos que lola_gemini_model y knowledge_base se pasarán a estas funciones
# para que no tengamos que inicializarlos aquí.

def perform_qa(user_query, lola_gemini_model, knowledge_base):
    """Herramienta para Preguntas y Respuestas directas. Muy estricta."""
    print("🧠 Usando Herramienta: Pregunta y Respuesta (Q&A)")
    
    persona_prompt = (
        "Eres un asistente de IA llamado Lola. Tu única tarea es responder preguntas basándote exclusivamente en la 'Información Relevante' proporcionada. "
        "REGLA CRÍTICA: Si la respuesta no está explícitamente en el texto, debes responder EXACTAMENTE: 'No tengo esa información específica en mis documentos.'"
    )
    
    # Lógica RAG (idéntica a la que ya tienes)
    results = knowledge_base.query(user_query, n_results=5)
    retrieved_content = []
    if results and results['documents'] and results['documents'][0]:
        retrieved_content = results['documents'][0]
    
    context_prompt = "\n\n**Información Relevante:**\n" + "\n---\n".join(retrieved_content)
    full_prompt = f"{persona_prompt}{context_prompt}\n\n**Consulta del Usuario:** {user_query}\n\n**Respuesta de Lola:**"
    
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