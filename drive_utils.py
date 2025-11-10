import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import time
import mimetypes
import streamlit as st # Add streamlit import

# Define the scopes Lola needs. Ensure these match what you configured in Google Cloud.
# NOTE: The original code used 'token.pickle', but we will use 'token.json' for consistency.
SCOPES = [
    'https://www.googleapis.com/auth/drive',        # Full Drive access
    'https://www.googleapis.com/auth/documents',    # For Google Docs
    'https://www.googleapis.com/auth/spreadsheets'  # For Google Sheets
]

# Modificamos la función para usar 'token.json' como en el flujo inicial.
def get_drive_service():
    """
    Authenticates with Google Drive. Works for both local development
    (using token.json) and Streamlit Cloud deployment (using st.secrets).
    """
    try:
        # DEPLOYMENT PATH: Use credentials from Streamlit secrets
        creds = Credentials.from_authorized_user_info(st.secrets["google_credentials"], SCOPES)
    except:
        # LOCAL DEVELOPMENT PATH: Use local token.json file
        creds = None
        TOKEN_FILE = 'token.json'
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Token expirado. Refrescando credenciales...")
                creds.refresh(Request())
            else:
                print("Iniciando nuevo flujo de autenticación...")
                if not os.path.exists('client_secret.json'):
                    raise FileNotFoundError("client_secret.json no encontrado.")
                flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)

            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def search_drive_files(service, query, mime_type=None, folder_id=None):
    """
    Searches Google Drive for files matching a query.
    """
    q_parts = [query]
    if mime_type:
        q_parts.append(f"mimeType='{mime_type}'")
    if folder_id:
        q_parts.append(f"'{folder_id}' in parents")

    full_query = " and ".join(q_parts)
    print(f"Searching Drive with query: {full_query}")

    results = []
    page_token = None
    while True:
        response = service.files().list(
            q=full_query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType, modifiedTime, parents)',
            pageToken=page_token
        ).execute()
        results.extend(response.get('files', []))
        page_token = response.get('nextPageToken', None)
        if not page_token:
            break
    return results

def download_file(service, file_id, file_name, destination_path='temp_docs'):
    """
    Downloads a file from Google Drive.
    Handles Google Docs/Sheets conversion to more portable formats.
    """
    os.makedirs(destination_path, exist_ok=True)
    file_metadata = service.files().get(fileId=file_id, fields='mimeType, name').execute()
    mime_type = file_metadata['mimeType']
    actual_file_name = file_metadata['name']

    download_format = None
    if mime_type == 'application/vnd.google-apps.document':
        download_format = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' # .docx
        extension = '.docx'
    elif mime_type == 'application/vnd.google-apps.spreadsheet':
        download_format = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' # .xlsx
        extension = '.xlsx'
    elif mime_type == 'application/vnd.google-apps.presentation':
        download_format = 'application/vnd.openxmlformats-officedocument.presentationml.presentation' # .pptx
        extension = '.pptx'
    elif mime_type == 'application/pdf':
        download_format = 'application/pdf'
        extension = '.pdf'
    elif mime_type.startswith('text/'): # Plain text
        download_format = 'text/plain'
        extension = '.txt'
    else: # Generic blob or unsupported type
        # Try to infer extension, or fallback to generic
        extension = os.path.splitext(actual_file_name)[1] or '.bin'
        download_format = mime_type # Download as is

    local_file_path = os.path.join(destination_path, f"{file_name}{extension}")

    request = None
    if download_format and mime_type.startswith('application/vnd.google-apps'):
        request = service.files().export_media(fileId=file_id, mimeType=download_format)
    else:
        request = service.files().get_media(fileId=file_id)

    fh = io.FileIO(local_file_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Downloading {actual_file_name}: {int(status.progress() * 100)}%")
    print(f"Downloaded: {local_file_path}")
    return local_file_path

def upload_file_to_drive(service, file_path, name, parent_folder_id=None, mime_type=None):
    """
    Uploads a file to Google Drive.
    """
    file_metadata = {'name': name}
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    # Infer MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream' # Default if cannot infer

    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id, name, parents').execute()
    print(f"File ID: {file.get('id')} uploaded as '{file.get('name')}'")
    return file

def update_file_in_drive(service, file_id, file_path, mime_type=None):
    """
    Updates an existing file in Google Drive.
    """
    # Infer MIME type if not provided
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream' # Default if cannot infer

    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    file = service.files().update(fileId=file_id, media_body=media, fields='id, name, modifiedTime').execute()
    print(f"File ID: {file.get('id')} updated. New modified time: {file.get('modifiedTime')}")
    return file

def list_all_files_in_folder_recursive(service, folder_id, query_conditions=""):
    """
    Recursively finds all files in a given Google Drive folder and its sub-folders.
    Handles pagination to ensure all files are found.

    Args:
        service: The authenticated Google Drive service object.
        folder_id: The ID of the root folder to start searching from.
        query_conditions: Optional additional query strings (e.g., for modification time).

    Returns:
        A list of file objects (dictionaries), excluding folders.
    """
    all_files = []
    folders_to_search = [folder_id]
    searched_folders = set()

    while folders_to_search:
        current_folder_id = folders_to_search.pop(0)
        if current_folder_id in searched_folders:
            continue
        
        searched_folders.add(current_folder_id)
        page_token = None

        while True:
            # Construct the query
            query = f"'{current_folder_id}' in parents and trashed = false"
            if query_conditions:
                query += f" and {query_conditions}"

            try:
                response = service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime)',
                    pageToken=page_token
                ).execute()

                for item in response.get('files', []):
                    # If the item is a folder, add it to the list to be searched
                    if item.get('mimeType') == 'application/vnd.google-apps.folder':
                        folders_to_search.append(item.get('id'))
                    # Otherwise, it's a file, so add it to our results
                    else:
                        all_files.append(item)

                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
            
            except Exception as e:
                print(f"An error occurred while accessing folder {current_folder_id}: {e}")
                break # Stop trying if a folder is inaccessible

    return all_files

# --- Your existing search_drive_files function should remain,
# as it's useful for targeted searches.
# Just ensure you use the new recursive function where needed.

def update_google_doc_content(doc_id, new_content):
    """
    Updates the content of a Google Doc.
    Note: This is more complex than a simple file upload.
    This example clears and inserts.
    """
    # Se crea un nuevo servicio de Docs, reusando las credenciales de Drive
    drive_service = get_drive_service()
    docs_service = build('docs', 'v1', credentials=drive_service._http.credentials) 
    
    # 1. Obtener el contenido actual para encontrar su longitud
    doc = docs_service.documents().get(documentId=doc_id).execute()
    # Determinar el final del documento para eliminar el contenido
    # Se necesita el índice final del último elemento de la sección de body/content
    try:
        doc_length = doc.get('body').get('content')[-1].get('endIndex') - 1
    except:
        # Si el documento está vacío, establecer la longitud en 1 (después del título)
        doc_length = 1

    requests = [
        # 1. Eliminar contenido existente (del índice 1 hasta el final)
        {
            'deleteContentRange': {
                'range': {
                    'segmentId': '',
                    'startIndex': 1,
                    'endIndex': doc_length
                }
            }
        },
        # 2. Insertar nuevo contenido en el índice 1 (después del título)
        {
            'insertText': {
                'location': {
                    'segmentId': '',
                    'startIndex': 1
                },
                'text': new_content
            }
        }
    ]
    result = docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    print(f"Google Doc '{doc_id}' actualizado.")
    return result