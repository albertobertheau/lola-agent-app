import os
import sys
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- This script is a self-contained test ---

def get_drive_service_for_test():
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly'] # Read-only is safer for a test
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def list_files_recursive_for_test(service, folder_id):
    all_files = []
    folders_to_search = [folder_id]
    searched_folders = set()
    while folders_to_search:
        current_folder_id = folders_to_search.pop(0)
        if current_folder_id in searched_folders: continue
        searched_folders.add(current_folder_id)
        page_token = None
        while True:
            try:
                response = service.files().list(q=f"'{current_folder_id}' in parents and trashed = false",
                                                spaces='drive', fields='nextPageToken, files(id, name, mimeType)',
                                                pageToken=page_token).execute()
                for item in response.get('files', []):
                    if item.get('mimeType') == 'application/vnd.google-apps.folder':
                        folders_to_search.append(item.get('id'))
                    else:
                        all_files.append(item)
                page_token = response.get('nextPageToken', None)
                if page_token is None: break
            except Exception as e:
                print(f"Error accessing folder {current_folder_id}: {e}")
                break
    return all_files

# --- Main Test Logic ---
if __name__ == '__main__':
    print("--- STARTING LOOP DIAGNOSTIC TEST ---")
    load_dotenv()
    
    root_folder_id = os.getenv("CHAINBRIEF_ROOT_FOLDER_ID")
    if not root_folder_id:
        print("ERROR: CHAINBRIEF_ROOT_FOLDER_ID not found in .env file.")
        sys.exit()

    print("Authenticating with Google Drive...")
    drive_service = get_drive_service_for_test()
    
    print(f"Searching for files in root folder: {root_folder_id}...")
    files_to_process = list_files_recursive_for_test(drive_service, root_folder_id)
    
    print(f"\nFound a total of {len(files_to_process)} files.")
    print("--- NOW STARTING THE TEST LOOP ---")
    
    file_counter = 0
    for file in files_to_process:
        file_counter += 1
        file_name = file.get('name', 'Unknown Name')
        
        print(f"\n>>> PROCESSING LOOP #{file_counter}: {file_name}")
        
        # We will add a hard stop to see if the loop even reaches the third item
        if file_counter == 3:
            print("\n>>> SUCCESS: The loop has successfully reached the 3rd item.")
            print("--- TEST COMPLETE ---")
            sys.exit() # This forces the script to stop here.

    print("\n--- LOOP FINISHED NATURALLY ---")
    if file_counter < 3:
        print(f"\n>>> FAILURE: The loop only ran {file_counter} time(s) and exited prematurely.")
        print("This confirms a deep environmental issue, as the code should not have stopped.")