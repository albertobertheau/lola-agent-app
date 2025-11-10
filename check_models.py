import os
import google.generativeai as genai
from dotenv import load_dotenv

print("--- Running Gemini Model Check ---")

try:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env file.")
        
    genai.configure(api_key=api_key)

    print("Successfully configured API key.")
    print("Fetching available models...\n")

    # List all available models
    for model in genai.list_models():
        # Check if the model supports the 'generateContent' method
        if 'generateContent' in model.supported_generation_methods:
            print(f"Model Name: {model.name}")
            # print(f"  - Description: {model.description}")
            # print(f"  - Methods: {model.supported_generation_methods}\n")

except Exception as e:
    print(f"An error occurred: {e}")

print("\n--- Check Complete ---")