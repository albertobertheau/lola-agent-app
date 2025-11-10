import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

try:
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        raise ValueError("La clave GEMINI_API_KEY no se encontró en el archivo .env.")
    
    genai.configure(api_key=API_KEY)
    
    # --- SOLUTION FOR 404 ERROR (Consistency) ---
    # Use the stable model name to prevent potential 404 errors during summarization.
    LLM_MODEL_NAME = 'models/gemini-pro-latest' 
    
    general_gemini_model = genai.GenerativeModel(LLM_MODEL_NAME)
    print(f"✅ Cliente Gemini configurado para operaciones generales usando '{LLM_MODEL_NAME}'.")

except Exception as e:
    print(f"❌ Error al inicializar el cliente Gemini para operaciones generales: {e}")
    general_gemini_model = None

def summarize_text_with_gemini(text_content, context_prompt="Eres Lola Agent, una experta en análisis de documentos. Tu tarea es resumir el siguiente texto en 5 puntos clave para una junta ejecutiva."):
    """
    Usa la API de Gemini para resumir el contenido de un documento.
    """
    if not general_gemini_model:
        return "Error: Cliente Gemini no inicializado para resumen."
        
    full_prompt = f"{context_prompt}\n\n--- TEXTO ---\n{text_content}"
    
    print("🧠 Enviando contenido a Gemini para resumen...")
    
    try:
        # This is a text generation call, which is correct for this file's purpose.
        response = general_gemini_model.generate_content(full_prompt)
        return response.text
        
    except Exception as e:
        return f"Error en la llamada a la API de Gemini: {e}"

if __name__ == '__main__':
    # This block allows you to test this file independently if you wish.
    documento_ejemplo = (
        "El informe trimestral indica que las ventas cayeron un 15% debido a problemas en la cadena de suministro. "
        "Sin embargo, la inversión en I+D aumentó un 20%, lo que generará dos nuevas patentes clave. "
        "La principal recomendación es diversificar proveedores en Asia para reducir riesgos para el próximo trimestre."
    )
    
    resumen = summarize_text_with_gemini(documento_ejemplo)
    
    print("\n--- RESUMEN GENERADO POR LOLA AGENT ---")
    print(resumen)