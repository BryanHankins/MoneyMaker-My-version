"""
youtube_auth.py — One-time YouTube OAuth setup
===============================================
Run this ONCE to get your YOUTUBE_REFRESH_TOKEN.
After running, copy the refresh token printed at the end into your .env file.

Steps:
1. Go to https://console.cloud.google.com
2. Create a project → Enable "YouTube Data API v3"
3. Create OAuth 2.0 credentials (Desktop App type)
4. Download credentials JSON → save as client_secrets.json in this folder
5. Run: python youtube_auth.py
6. A browser window opens → log in → grant access
7. Copy the refresh token printed into your .env as YOUTUBE_REFRESH_TOKEN
"""

import json
from pathlib import Path

def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Run first: pip install google-auth-oauthlib")
        return

    secrets_file = Path("client_secrets.json")
    if not secrets_file.exists():
        print("ERROR: client_secrets.json not found.")
        print("Download it from Google Cloud Console → APIs → Credentials → OAuth 2.0 Client ID")
        return

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print("✅ Authentication successful!")
    print("=" * 60)
    print(f"\nYOUTUBE_CLIENT_ID={creds.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={creds.client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
    print("\nCopy these three values into your .env file.")

    # Also save to a local file for reference
    out = {
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
    }
    Path("youtube_credentials.json").write_text(json.dumps(out, indent=2))
    print("\nAlso saved to youtube_credentials.json (keep this private!)")


if __name__ == "__main__":
    main()
