"""
tasks/email_send.py

Sends the audit report via Gmail SMTP (smtplib).
- Personalised subject line
- HTML email body with context about the report
- PDF attached
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text       import MIMEText
from email.mime.base       import MIMEBase
from email                 import encoders
from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, YOUR_COMPANY_NAME


# ── Email body template ───────────────────────────────────────────────────────

def _build_email_html(lead: dict, drive_url: str = "") -> str:
    drive_section = ""
    if drive_url:
        drive_section = f"""
        <p style="margin:24px 0 0;">
          <a href="{drive_url}"
             style="background:#4f46e5;color:white;padding:10px 20px;
                    border-radius:6px;text-decoration:none;font-weight:600;
                    font-size:13px;">
            View report online →
          </a>
        </p>
        """

    return f"""
    <html><body style="font-family:-apple-system,sans-serif;color:#1f2937;
                        line-height:1.7;max-width:580px;margin:0 auto;padding:32px 24px;">

      <p style="color:#6b7280;font-size:12px;text-transform:uppercase;
                letter-spacing:1px;font-weight:600;">{YOUR_COMPANY_NAME}</p>

      <h2 style="font-size:22px;font-weight:700;margin:8px 0 24px;color:#111827;">
        Hi {lead['name']}, your intelligence brief is ready.
      </h2>

      <p>
        Thanks for reaching out. I've put together a personalised audit of
        <strong>{lead['company']}</strong> — it covers your current positioning,
        the gaps I spotted based on what you shared, and where I see the
        clearest opportunity for us to work together.
      </p>

      <p>
        You'll find the full brief attached as a PDF. It's built specifically
        around what you mentioned — <em>"{lead['pain_points'][:120]}..."</em> —
        so nothing in there is generic.
      </p>

      <p>
        Happy to walk through any of it on a 20-minute call whenever suits you.
        Just reply here and we'll find a time.
      </p>

      {drive_section}

      <p style="margin-top:40px;padding-top:24px;border-top:1px solid #e5e7eb;
                font-size:13px;color:#6b7280;">
        Best,<br/>
        <strong style="color:#111827;">{YOUR_COMPANY_NAME} Team</strong><br/>
        <a href="mailto:{SMTP_USER}" style="color:#4f46e5;">{SMTP_USER}</a>
      </p>

      <p style="font-size:11px;color:#9ca3af;margin-top:16px;">
        This report was prepared exclusively for {lead['name']} at {lead['company']}.
      </p>

    </body></html>
    """


# ── Sender ────────────────────────────────────────────────────────────────────

async def send_email(lead: dict, pdf_path: str, drive_url: str = "") -> bool:
    """
    Send the personalised report email with PDF attachment.
    Returns True on success, raises on failure.
    """
    msg = MIMEMultipart("alternative")

    # Subject — specific to the company, not generic
    msg["Subject"] = (
        f"Your {lead['company']} intelligence brief — "
        f"personalised audit from {YOUR_COMPANY_NAME}"
    )
    msg["From"]    = SMTP_USER
    msg["To"]      = lead["email"]

    # Plain-text fallback
    plain = (
        f"Hi {lead['name']},\n\n"
        f"Your personalised audit for {lead['company']} is attached.\n\n"
        f"Best,\n{YOUR_COMPANY_NAME} Team"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_email_html(lead, drive_url), "html"))

    # Attach PDF
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(pdf_path)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    # Send via Gmail SMTP
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, lead["email"], msg.as_string())

    return True
