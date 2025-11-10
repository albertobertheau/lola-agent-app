import os
import time
from drive_utils import get_drive_service, search_drive_files, download_file, upload_file_to_drive, update_file_in_drive

# --- 1. Autenticación ---
print("--- 1. Autenticando a Lola Agent con Google Drive ---")
try:
    # La primera llamada a get_drive_service() activará el navegador para la autorización.
    drive_service = get_drive_service()
    print("✅ Servicio de Google Drive obtenido. Autenticación exitosa.")
except Exception as e:
    print(f"❌ Error durante la autenticación: {e}")
    print("Asegúrate de que 'client_secret.json' esté en la carpeta del proyecto.")
    exit()

# --- 2. Búsqueda de Archivos (Ejemplo) ---
print("\n--- 2. Buscando archivos (Documentos de Google) ---")
# Busca los 5 documentos de Google Docs más recientes que no están en la papelera
try:
    search_query = "mimeType='application/vnd.google-apps.document' and trashed = false"
    documents = search_drive_files(drive_service, query=search_query)

    if not documents:
        print("🔍 No se encontraron Google Docs. Creando un archivo de prueba para continuar...")
        
        # Crea un archivo local temporal para subir
        test_file_path = 'temp_docs/test_upload.txt'
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, 'w') as f:
            f.write("Este es un archivo de prueba creado por Lola Agent.")

        # Sube el archivo como un Google Doc (la API lo convierte)
        uploaded_doc = upload_file_to_drive(
            drive_service,
            file_path=test_file_path,
            name="Lola Agent - Documento de Prueba",
            mime_type='application/vnd.google-apps.document' # Pide a Drive que lo convierta a Doc
        )
        documents = [uploaded_doc]
        time.sleep(2) # Espera un poco para que Drive lo procese
        
    print(f"🔍 Encontrados {len(documents)} documentos. Detalles del primero:")
    first_doc = documents[0]
    print(f"  ID: {first_doc.get('id')}")
    print(f"  Nombre: {first_doc.get('name')}")
    print(f"  Tipo MIME: {first_doc.get('mimeType')}")

except Exception as e:
    print(f"❌ Error en la búsqueda de archivos: {e}")
    exit()

# --- 3. Descarga del Documento de Prueba ---
print("\n--- 3. Descargando el documento de prueba (con conversión a .docx) ---")
downloaded_path = None
try:
    # Usamos el primer documento encontrado (o el que creamos)
    downloaded_path = download_file(
        drive_service,
        file_id=first_doc['id'],
        file_name="Lola_Test_Doc",
        destination_path='temp_downloads'
    )
    print(f"✅ Descarga completada. Archivo guardado en: {downloaded_path}")

except Exception as e:
    print(f"❌ Error en la descarga: {e}")


# --- 4. Eliminación de Archivos de Prueba (Limpieza) ---
if downloaded_path and os.path.exists(downloaded_path):
    # La limpieza solo se intenta si el archivo fue creado por el script.
    if documents[0].get('name') == "Lola Agent - Documento de Prueba":
        print("\n--- 4. Eliminando archivo de prueba ---")
        try:
            drive_service.files().delete(fileId=documents[0]['id']).execute()
            print("🗑️ Archivo de prueba eliminado de Google Drive.")
            os.remove(downloaded_path)
            print(f"🗑️ Archivo local '{downloaded_path}' eliminado.")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar el archivo de prueba. Por favor, elimínalo manualmente. Error: {e}")