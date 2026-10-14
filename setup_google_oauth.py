"""
Google Workspace OAuth Setup Utility for Jarvis.
Generates token.json from credentials.json with Gmail, Calendar, Tasks, and Drive scopes.
"""

import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import config

def run_oauth_flow():
    creds_path = config.GOOGLE_CREDENTIALS_FILE
    token_path = config.GOOGLE_TOKEN_FILE

    print("=" * 65)
    print("      JARVIS GOOGLE WORKSPACE OAUTH INITIALIZATION")
    print("=" * 65)

    if not creds_path.exists():
        print(f"\n[!] Error: OAuth Client credentials file not found at:")
        print(f"    {creds_path}\n")
        print("To generate 'credentials.json':")
        print("  1. Visit Google Cloud Console: https://console.cloud.google.com/")
        print("  2. Create or select a project (e.g. 'Jarvis-Personal-Agent').")
        print("  3. Enable the following APIs in 'APIs & Services' -> 'Library':")
        print("     - Gmail API")
        print("     - Google Calendar API")
        print("     - Google Tasks API")
        print("     - Google Drive API")
        print("  4. Configure 'OAuth consent screen' as 'External' or 'Internal' and add your email.")
        print("  5. Navigate to 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'.")
        print("  6. Choose Application Type: 'Desktop App'.")
        print("  7. Download the client secret JSON file, rename it to 'credentials.json',")
        print(f"     and place it at: {creds_path}")
        print("=" * 65)
        sys.exit(1)

    print(f"[*] Found credentials at: {creds_path}")
    print("[*] Requesting authorization for scopes:")
    for scope in config.GOOGLE_SCOPES:
        print(f"    - {scope}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(creds_path),
        scopes=config.GOOGLE_SCOPES
    )

    print("\n[*] Launching browser for Google authentication...")
    print("    If a browser window does not open automatically, visit the URL in the terminal.")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    # Save credentials into token.json
    with open(token_path, "w", encoding="utf-8") as token_file:
        token_file.write(creds.to_json())

    print(f"\n[+] Successfully saved OAuth token to: {token_path}")

    # Verify authorization
    print("\n[*] Verifying authorization by testing Google API connections...")
    try:
        gmail_service = build("gmail", "v1", credentials=creds)
        profile = gmail_service.users().getProfile(userId="me").execute()
        user_email = profile.get("emailAddress", "Unknown")
        print(f"[+] Gmail connection verified! Account: {user_email}")

        calendar_service = build("calendar", "v3", credentials=creds)
        cals = calendar_service.calendarList().list(maxResults=5).execute()
        print(f"[+] Calendar connection verified! Found {len(cals.get('items', []))} calendar(s).")

        tasks_service = build("tasks", "v1", credentials=creds)
        task_lists = tasks_service.tasklists().list(maxResults=5).execute()
        print(f"[+] Google Tasks verified! Found {len(task_lists.get('items', []))} task list(s).")

        drive_service = build("drive", "v3", credentials=creds)
        about = drive_service.about().get(fields="user").execute()
        print(f"[+] Google Drive verified! Drive user: {about.get('user', {}).get('displayName', 'User')}")

        print("\n" + "=" * 65)
        print(" [SUCCESS] Google Workspace integration is fully configured and ready!")
        print("=" * 65)
    except Exception as e:
        print(f"[!] Warning during verification: {e}")
        print("    Token was written to disk and may still work. Review any disabled APIs.")

if __name__ == "__main__":
    run_oauth_flow()
