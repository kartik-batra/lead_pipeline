"""
tasks/pipeline.py

Full pipeline orchestrator. Called as a background asyncio task.

Stages:
  1. Log lead to Google Sheet (status: processing)
  2. Enrich company data
  3. Generate AI report (Groq two-pass)
  4. Render PDF (WeasyPrint)
  5. Upload to Google Drive
  6. Send email (SMTP)
  7. Update Sheet row → status: sent + Drive URL
  8. Update SQLite lead record throughout
"""

import os
import re
from datetime import datetime
from sqlmodel import Session, select

from models import Lead, engine
from tasks.enrich         import enrich_company
from tasks.generate       import generate_report
from tasks.pdf_gen        import render_pdf
from tasks.email_send     import send_email
from tasks.sheets_logger  import log_lead, update_status
from tasks.drive_uploader import upload_pdf


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _set_status(lead_id: int, status: str, error: str = None):
    with Session(engine) as s:
        lead = s.get(Lead, lead_id)
        if lead:
            lead.status    = status
            lead.error_msg = error
            if status == "sent":
                lead.completed_at = datetime.utcnow()
            s.add(lead)
            s.commit()


def _save_outputs(lead_id: int, pdf_path: str, drive_url: str, sheet_row: int):
    with Session(engine) as s:
        lead = s.get(Lead, lead_id)
        if lead:
            lead.pdf_path  = pdf_path
            lead.drive_url = drive_url
            lead.sheet_row = sheet_row
            s.add(lead)
            s.commit()


def _get_lead_dict(lead_id: int) -> dict:
    with Session(engine) as s:
        lead = s.get(Lead, lead_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")
        return {
            "id":          lead.id,
            "name":        lead.name,
            "email":       lead.email,
            "company":     lead.company,
            "website":     lead.website,
            "industry":    lead.industry,
            "pain_points": lead.pain_points,
        }


# ── Main pipeline ──────────────────────────────────────────────────────────────

async def run_pipeline(lead_id: int):
    """
    End-to-end pipeline. Runs as a background asyncio task.
    All failures are caught, logged to DB, and Sheet is updated.
    """
    print(f"\n[pipeline] ▶ Starting for lead_id={lead_id}")

    try:
        lead = _get_lead_dict(lead_id)
    except Exception as e:
        print(f"[pipeline] ✗ Could not load lead: {e}")
        return

    sheet_row = -1

    try:
        # ── Step 1: Log to Google Sheet ───────────────────────────────────────
        print("[pipeline] 1/7 Logging to Google Sheet...")
        _set_status(lead_id, "processing")
        sheet_row = log_lead(lead, status="processing")

        # ── Step 2: Enrich ────────────────────────────────────────────────────
        print("[pipeline] 2/7 Enriching company data...")
        _set_status(lead_id, "enriching")
        enriched = await enrich_company(lead)
        print(f"           Tech stack: {enriched.get('tech_stack')}")
        print(f"           Wiki found: {'yes' if enriched.get('wiki_summary') else 'no'}")

        # ── Step 3: Generate report ───────────────────────────────────────────
        print("[pipeline] 3/7 Generating AI report (two-pass)...")
        _set_status(lead_id, "generating")
        report_markdown = await generate_report(lead, enriched)
        word_count = len(report_markdown.split())
        print(f"           Report: {word_count} words")

        # ── Step 4: Render PDF ────────────────────────────────────────────────
        print("[pipeline] 4/7 Rendering PDF...")
        _set_status(lead_id, "rendering")
        pdf_path = render_pdf(report_markdown, lead)
        size_kb = os.path.getsize(pdf_path) // 1024
        print(f"           PDF: {os.path.basename(pdf_path)} ({size_kb} KB)")

        # ── Step 5: Upload to Drive ───────────────────────────────────────────
        print("[pipeline] 5/7 Uploading to Google Drive...")
        filename  = os.path.basename(pdf_path)
        drive_url = upload_pdf(pdf_path, filename)
        print(f"           Drive URL: {drive_url or 'upload failed (non-critical)'}")

        # Save outputs to DB
        _save_outputs(lead_id, pdf_path, drive_url, sheet_row)

        # ── Step 6: Send email ────────────────────────────────────────────────
        print("[pipeline] 6/7 Sending email...")
        _set_status(lead_id, "sending")
        await send_email(lead, pdf_path, drive_url)
        print(f"           Email sent to {lead['email']}")

        # ── Step 7: Update Sheet ──────────────────────────────────────────────
        print("[pipeline] 7/7 Updating Google Sheet...")
        update_status(sheet_row, "sent", drive_url)

        # Mark complete
        _set_status(lead_id, "sent")
        print(f"[pipeline] ✓ Complete for {lead['company']} (lead_id={lead_id})\n")

    except Exception as e:
        error_msg = str(e)
        print(f"[pipeline] ✗ Failed at lead_id={lead_id}: {error_msg}")
        _set_status(lead_id, "failed", error=error_msg)
        if sheet_row > 0:
            update_status(sheet_row, f"failed: {error_msg[:60]}")
        raise
