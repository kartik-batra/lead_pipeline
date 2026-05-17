from dotenv import load_dotenv
import os

load_dotenv()

# Groq
GROQ_API_KEY        = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL          = "meta-llama/llama-4-scout-17b-16e-instruct"

# SerpAPI
SERPAPI_KEY         = os.getenv("SERPAPI_KEY", "")

# Email
SMTP_HOST           = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT           = int(os.getenv("SMTP_PORT", 587))
SMTP_USER           = os.getenv("SMTP_USER", "")
SMTP_PASSWORD       = os.getenv("SMTP_PASSWORD", "")

# Your company branding
YOUR_COMPANY_NAME    = os.getenv("YOUR_COMPANY_NAME", "Your Company")

# Google APIs
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/service_account.json")
SHEETS_SPREADSHEET_ID   = os.getenv("SHEETS_SPREADSHEET_ID", "")
DRIVE_FOLDER_ID         = os.getenv("DRIVE_FOLDER_ID", "")

# App
DATABASE_URL  = os.getenv("DATABASE_URL", "sqlite:///./leads.db")
REPORTS_DIR   = os.getenv("REPORTS_DIR", "reports")

# Ensure reports directory exists
os.makedirs(REPORTS_DIR, exist_ok=True)
