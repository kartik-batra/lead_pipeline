# Lead Intelligence Automation Pipeline

A fully automated lead intake and outreach system. When a prospect submits a form, the pipeline automatically enriches their company data, generates a personalised AI audit report, renders it as a branded PDF, archives it to Google Drive, logs the lead to Google Sheets, and delivers the report via email — all without human intervention.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup Guide](#setup-guide)
- [Running the App](#running-the-app)
- [API Reference](#api-reference)
- [Testing the Pipeline](#testing-the-pipeline)
- [Fallback & Resilience Design](#fallback--resilience-design)
- [Configuration Reference](#configuration-reference)

---

## How It Works

```
Prospect submits form
        │
        ▼
FastAPI accepts lead → saves to SQLite → returns 202 immediately
        │
        ▼ (background asyncio task)
┌───────────────────────────────────────────┐
│  Stage 1 │ Log to Google Sheets           │
│  Stage 2 │ Enrich (website + SerpAPI      │
│           │  + Wikipedia) concurrently    │
│  Stage 3 │ Generate report — Groq         │
│           │  Pass 1: analyst JSON         │
│           │  Pass 2: polished markdown    │
│  Stage 4 │ Render branded PDF             │
│  Stage 5 │ Upload PDF to Google Drive     │
│  Stage 6 │ Send personalised email        │
│  Stage 7 │ Update Sheet → status: sent    │
└───────────────────────────────────────────┘
        │
        ▼
Lead marked "sent" in SQLite
Admin dashboard updated at /leads
```

The form submission endpoint returns instantly. The entire pipeline runs in the background and typically completes in 30–60 seconds depending on network latency.

---

## Architecture

| Layer | Choice | Why |
|---|---|---|
| API server | FastAPI + Uvicorn | Async-native, fast, auto-docs at `/docs` |
| Background jobs | `asyncio` | Zero overhead for a local prototype |
| Web scraping | `httpx` + BeautifulSoup4 | Async HTTP, robust HTML parsing |
| News & competitors | SerpAPI | 100 free searches/month, reliable |
| Company data | Wikipedia REST API | Completely free, no key required |
| AI generation | Groq | Free tier, very fast |
| PDF rendering | WeasyPrint + Jinja2 | CSS-based, professional output |
| Email | Gmail SMTP via `smtplib` | Free, no third-party dependency |
| Database | SQLite + SQLModel | Zero setup, Pydantic-native ORM |
| Sheets logging | Google Sheets API | Live leads tracker |
| PDF archive | Google Drive API | Shareable link in every email |

### AI Report: Two-Pass Generation

The report is generated in two Groq calls to maximise quality:

**Pass 1 — Analyst** (`temperature=0.2`): Extracts structured JSON insights from raw enrichment data — business model, top pain, best engagement hook, competitor intel, next steps.

**Pass 2 — Writer** (`temperature=0.4`): Uses those structured insights as an analytical backbone to write the full markdown report, grounded in specifics rather than generic observations.

This separation ensures analytical reasoning happens before prose writing, producing noticeably sharper, more specific reports.

---

## Project Structure

```
lead_pipeline/
│
├── main.py                  # FastAPI app, endpoints, admin dashboard
├── models.py                # SQLModel Lead table + Pydantic form schema
├── config.py                # All settings loaded from .env
|
├── tasks/
│   ├── __init__.py 
│   ├── pipeline.py          # Orchestrator — runs all 7 stages in sequence
│   ├── enrich.py            # Company enrichment (3 sources, concurrent)
│   ├── generate.py          # Two-pass Groq report generation
│   ├── pdf_gen.py           # Markdown → HTML → WeasyPrint PDF
│   ├── email_send.py        # Gmail SMTP with HTML body + PDF attachment
│   ├── sheets_logger.py     # Google Sheets append + status update
│   └── drive_uploader.py    # Google Drive upload + shareable link
│
├── templates/
│   └── report.html          # Jinja2 PDF template (branded cover + report)
│
├── credentials/             # Git-ignored — put service_account.json here
├── reports/                 # Git-ignored — generated PDFs saved here
│
├── requirements.txt
├── .env.example             # Copy to .env and fill in your keys
└── .gitignore
```

---

## Tech Stack

| Concern | Tool | Cost |
|---|---|---|
| API server | FastAPI + Uvicorn | Free |
| Scraping | httpx + BeautifulSoup4 | Free |
| News / competitors | SerpAPI | Free (100 req/month) |
| Company facts | Wikipedia REST API | Free forever |
| AI report | Groq | Free |
| PDF | WeasyPrint + Jinja2 | Free |
| Email | Gmail SMTP | Free |
| Database | SQLite + SQLModel | Free |
| Sheets logging | Google Sheets API | Free |
| PDF archive | Google Drive API | Free |

**Total running cost: $0**

---

## Prerequisites

- Python 3.11+
- A Gmail account (for sending emails)
- A Groq account (free at [console.groq.com](https://console.groq.com))
- A SerpAPI account (free at [serpapi.com](https://serpapi.com))
- A Google Cloud project (free — for Sheets + Drive)

---

## Setup Guide

### 1. Clone and install

```bash
git clone <your-repo-url>
cd lead_pipeline

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Copy the environment file

```bash
cp .env.example .env
```

Open `.env` and fill in each value. The sections below explain how to get each key.

---

### 3. Get your Groq API key

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Click **API Keys → Create API Key**
3. Copy the key into `.env`:

```dotenv
GROQ_API_KEY=gsk_your_key_here
```

---

### 4. Get your SerpAPI key

1. Go to [serpapi.com](https://serpapi.com) and sign up (free — 100 searches/month)
2. Copy your key from the dashboard into `.env`:

```dotenv
SERPAPI_KEY=your_serpapi_key_here
```

> **Note:** SerpAPI is optional. If omitted, the pipeline skips news and competitor enrichment and generates the report from website + Wikipedia data only.

---

### 5. Set up Gmail SMTP

You need a **Gmail App Password** — not your regular Gmail password.

1. Enable 2-Step Verification on your Google account at [myaccount.google.com/security](https://myaccount.google.com/security)
2. Go to **Security → 2-Step Verification → App Passwords**
3. Select app: **Mail**, device: **Other** → name it `lead-pipeline` → Generate
4. Copy the 16-character password into `.env`:

```dotenv
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop     # the 16-char app password (spaces are fine)
```

---

### 6. Set up Google Sheets + Drive (optional)

> **Skip this for a quick prototype.**

**Step 1 — Create a Google Cloud project**

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown → **New Project** → create it

**Step 2 — Enable APIs**

In **APIs & Services → Library**, enable:
- Google Sheets API
- Google Drive API

**Step 3 — Create a service account**

1. Go to **APIs & Services → Credentials → Create Credentials → Service Account**
2. Give it any name (e.g. `lead-pipeline-bot`) → click through with defaults
3. Click the service account → **Keys tab → Add Key → Create new key → JSON**
4. Move the downloaded file to `credentials/service_account.json`

**Step 4 — Share your Sheet and Drive folder**

The service account has its own email address (find it in the JSON as `client_email`, ending in `.iam.gserviceaccount.com`).

- Open your **Google Sheet** → Share → paste the `client_email` → **Editor**
- Open your **Drive folder** → right-click → Share → paste the `client_email` → **Editor**

**Step 5 — Add IDs to `.env`**

```dotenv
# From your Sheet URL: /spreadsheets/d/THIS_PART/edit
SHEETS_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms

# From your Drive folder URL: /drive/folders/THIS_PART
DRIVE_FOLDER_ID=1A2B3C4D5E6F7G8H9I0J

# Enable Google integrations
USE_GOOGLE=true
```

> **Cost:** Google Sheets API and Drive API are both completely free. No billing surprises.

---

### 7. Set your company details

```dotenv
YOUR_COMPANY_NAME=Acme Solutions
YOUR_COMPANY_TAGLINE=We help B2B companies scale their revenue operations
```

---

## Running the App

```bash
python -m uvicorn main:app --reload --port 8000
```

Open:
- **API docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Admin dashboard:** [http://localhost:8000/leads](http://localhost:8000/leads)
- **Health check:** [http://localhost:8000/health](http://localhost:8000/health)


---

## API Reference

### `POST /submit-lead`

Accepts a lead form submission and starts the pipeline in the background.

**Request body:**

```json
{
  "name":        "Priya Sharma",
  "email":       "priya@example.com",
  "company":     "Razorpay",
  "website":     "https://razorpay.com",
  "industry":    "Fintech / Payments",
  "pain_points": "Struggling with enterprise onboarding and compliance automation"
}
```

**Response (202 Accepted):**

```json
{
  "id":     1,
  "status": "pending",
  "msg":    "Thanks Priya! Your personalised report for Razorpay is being prepared and will arrive at priya@example.com shortly."
}
```

---

### `GET /lead/{id}/status`

Poll the pipeline status for a specific lead.

```bash
curl http://localhost:8000/lead/1/status
```

```json
{
  "id":     1,
  "status": "generating",
  "msg":    "Generating your personalised audit report..."
}
```

**Status lifecycle:**

```
pending → enriching → generating → rendering → sending → sent
                                                       → failed
```

---

### `GET /leads`

HTML admin dashboard showing all leads, their pipeline status, and links to generated reports. Auto-refreshes every 10 seconds.

---

### `GET /health`

```json
{ "status": "ok" }
```

---

## Testing the Pipeline

**Quick test with curl:**

```bash
curl -X POST http://localhost:8000/submit-lead \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Raj Kumar",
    "email": "your_actual_email@gmail.com",
    "company": "Freshworks",
    "website": "https://freshworks.com",
    "industry": "SaaS / CRM",
    "pain_points": "Enterprise sales cycles are too long and onboarding takes weeks"
  }'
```

**Watch the pipeline run:**

The terminal shows each stage as it completes:

```
INFO  pipeline  ▶ Starting for lead_id=1
INFO  pipeline  1/7 Logging to Google Sheet...
INFO  pipeline  2/7 Enriching company data...
INFO  enrich    Website scraped — 6 tech signals
INFO  enrich    SerpAPI — 4 news items
INFO  enrich    Wikipedia — 'Freshworks' found, founded=2010
INFO  enrich    Enrichment done — quality=85/100
INFO  pipeline  3/7 Generating AI report (two-pass)...
INFO  generate  Analyst pass complete — JSON parsed successfully
INFO  generate  Writer pass complete — 742 words
INFO  pipeline  4/7 Rendering PDF...
INFO  pipeline  5/7 Uploading to Google Drive...
INFO  pipeline  6/7 Sending email...
INFO  pipeline  7/7 Updating Google Sheet...
INFO  pipeline  ✓ Complete for Freshworks (lead_id=1)
```

Then check your inbox — the report should arrive within 60 seconds of submission.

---

## Fallback & Resilience Design

The pipeline is designed to always complete, even when external services fail.

| Failure scenario | Behaviour |
|---|---|
| Website unreachable | Logged as warning; report generated from SerpAPI + Wikipedia data |
| SerpAPI key missing | Skipped silently; enrichment continues with other sources |
| Wikipedia no article | Empty string returned; report acknowledges limited data |
| All enrichment fails | Report generated from form data only with low-confidence language |
| Groq JSON malformed (Pass 1) | Falls back to single-pass report generation |
| Google Sheets/Drive unavailable | Logged as warning; email still sent; PDF saved locally |
| Email delivery fails | Lead marked `failed` in DB; error logged with full traceback |

Every enrichment source uses a **2-attempt retry** with a short backoff before giving up. The `data_quality` score (0–100) from enrichment is passed to the report generator, which calibrates its language accordingly — assertive when data is rich, appropriately hedged when it isn't.

All errors are written to `logs/pipeline.log` with timestamps for debugging.

---

## Configuration Reference

Full `.env` reference:

```dotenv
# ── AI ────────────────────────────────────────────
GROQ_API_KEY=                    # Required — get free at console.groq.com

# ── Enrichment ────────────────────────────────────
SERPAPI_KEY=                     # Optional — 100 free/month at serpapi.com

# ── Email ─────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=                       # Your Gmail address
SMTP_PASSWORD=                   # Gmail App Password (16 chars)

# ── Branding ──────────────────────────────────────
YOUR_COMPANY_NAME=Your company name
YOUR_COMPANY_TAGLINE=company tagline

# ── Google (optional) ─────────────────────────────
USE_GOOGLE=false                 # Set to true to enable Sheets + Drive
GOOGLE_CREDENTIALS_PATH=credentials/service_account.json
SHEETS_SPREADSHEET_ID=           # From your Google Sheet URL
DRIVE_FOLDER_ID=                 # From your Google Drive folder URL

# ── App ───────────────────────────────────────────
DATABASE_URL=sqlite:///./leads.db
REPORTS_DIR=reports
```