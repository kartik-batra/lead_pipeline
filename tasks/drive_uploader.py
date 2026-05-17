"""
tasks/drive_uploader.py

Uploads the generated PDF to a Google Drive folder and returns its shareable URL.
"""

from googleapiclient.discovery import build
from googleapiclient.http      import MediaFileUpload
from google.oauth2             import service_account
from config import GOOGLE_CREDENTIALS_PATH, DRIVE_FOLDER_ID

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _client():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_pdf(pdf_path: str, filename: str) -> str:
    """
    Upload a PDF to the configured Drive folder.
    Sets 'anyone with link can view' permission.
    Returns the webViewLink URL, or empty string on failure.
    """
    try:
        svc = _client()

        file_meta = {
            "name":    filename,
            "parents": [DRIVE_FOLDER_ID],
        }
        media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)

        uploaded = svc.files().create(
            body=file_meta,
            media_body=media,
            fields="id,webViewLink",
        ).execute()

        # Grant anyone-with-link read access
        svc.permissions().create(
            fileId=uploaded["id"],
            body={"type": "anyone", "role": "reader"},
        ).execute()

        return uploaded.get("webViewLink", "")

    except Exception as e:
        print(f"[drive] upload_pdf failed: {e}")
        return ""
