"""
tasks/sheets_logger.py

Appends lead data to a Google Sheet and updates status after delivery.
Columns: Name | Email | Company | Website | Industry | Timestamp | Status | Drive URL
"""

from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime
from config import GOOGLE_CREDENTIALS_PATH, SHEETS_SPREADSHEET_ID

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_RANGE = "Sheet1"


def _client():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def ensure_header():
    """Write the header row if the sheet is empty."""
    svc = _client()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEETS_SPREADSHEET_ID,
        range=f"{SHEET_RANGE}!A1:H1"
    ).execute()
    if not result.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=SHEETS_SPREADSHEET_ID,
            range=f"{SHEET_RANGE}!A1",
            valueInputOption="RAW",
            body={"values": [["Name","Email","Company","Website","Industry","Submitted At","Status","Drive URL"]]}
        ).execute()


def log_lead(lead: dict, status: str = "processing") -> int:
    """
    Append a new lead row. Returns the row number for later status updates.
    """
    try:
        ensure_header()
        svc = _client()
        row = [
            lead.get("name", ""),
            lead.get("email", ""),
            lead.get("company", ""),
            lead.get("website", ""),
            lead.get("industry", ""),
            datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            status,
            "",   # Drive URL — filled in later
        ]
        result = svc.spreadsheets().values().append(
            spreadsheetId=SHEETS_SPREADSHEET_ID,
            range=f"{SHEET_RANGE}!A:H",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        # Parse row number from updatedRange e.g. "Sheet1!A5:H5"
        updated_range = result["updates"]["updatedRange"]
        row_number = int(updated_range.split("!A")[1].split(":")[0])
        return row_number

    except Exception as e:
        print(f"[sheets] log_lead failed: {e}")
        return -1


def update_status(row_number: int, status: str, drive_url: str = ""):
    """Update the Status and Drive URL columns for a specific row."""
    if row_number < 1:
        return
    try:
        svc = _client()
        svc.spreadsheets().values().update(
            spreadsheetId=SHEETS_SPREADSHEET_ID,
            range=f"{SHEET_RANGE}!G{row_number}:H{row_number}",
            valueInputOption="RAW",
            body={"values": [[status, drive_url]]},
        ).execute()
    except Exception as e:
        print(f"[sheets] update_status failed: {e}")
