"""
main.py

FastAPI application — lead intake form, status check, and admin dashboard.

Endpoints:
  POST /submit-lead        — accepts the form, kicks off background pipeline
  GET  /lead/{id}/status   — check pipeline status for a lead
  GET  /leads              — admin view of all leads (basic HTML table)
  GET  /health             — healthcheck
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from models import Lead, LeadFormInput, LeadStatusResponse, create_db, get_session
from tasks.pipeline import run_pipeline


# ── App startup ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    print("✓ Database ready (SQLite)")
    yield

app = FastAPI(
    title="Lead Intelligence Pipeline",
    description="Automated lead enrichment, AI report generation, and email delivery",
    version="1.0.0",
    lifespan=lifespan,
)


# ── POST /submit-lead ──────────────────────────────────────────────────────────

@app.post("/submit-lead", response_model=LeadStatusResponse, status_code=202)
async def submit_lead(
    form: LeadFormInput,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """
    Accept a new lead form submission.
    Immediately returns 202 Accepted and runs the full pipeline in the background.
    """
    # Persist to DB
    lead = Lead(
        name        = form.name,
        email       = form.email,
        company     = form.company,
        website     = str(form.website),
        industry    = form.industry,
        pain_points = form.pain_points,
        status      = "pending",
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)

    # Fire pipeline as a background task
    background_tasks.add_task(run_pipeline, lead.id)

    print(f"\n✓ Lead accepted: {lead.company} (id={lead.id}) — pipeline starting...")

    return LeadStatusResponse(
        id=lead.id,
        status="pending",
        msg=(
            f"Thanks {form.name}! Your personalised report for {form.company} "
            f"is being prepared and will arrive at {form.email} shortly."
        )
    )


# ── GET /lead/{id}/status ──────────────────────────────────────────────────────

@app.get("/lead/{lead_id}/status", response_model=LeadStatusResponse)
def get_lead_status(lead_id: int, session: Session = Depends(get_session)):
    """Poll the pipeline status for a specific lead."""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    messages = {
        "pending":    "Your submission was received. Pipeline starting...",
        "processing": "Logging your details and preparing enrichment...",
        "enriching":  "Researching your company from multiple sources...",
        "generating": "Generating your personalised audit report...",
        "rendering":  "Rendering your report as a PDF...",
        "sending":    "Sending your report via email...",
        "sent":       f"Report delivered to {lead.email}. Check your inbox!",
        "failed":     f"Pipeline error: {lead.error_msg}",
    }

    return LeadStatusResponse(
        id=lead.id,
        status=lead.status,
        msg=messages.get(lead.status, lead.status),
    )


# ── GET /leads (admin dashboard) ───────────────────────────────────────────────

@app.get("/leads", response_class=HTMLResponse)
def list_leads(session: Session = Depends(get_session)):
    """Simple HTML admin dashboard showing all leads and their status."""
    leads = session.exec(select(Lead).order_by(Lead.id.desc())).all()

    status_colors = {
        "pending":    "#9ca3af",
        "processing": "#f59e0b",
        "enriching":  "#3b82f6",
        "generating": "#8b5cf6",
        "rendering":  "#f97316",
        "sending":    "#06b6d4",
        "sent":       "#10b981",
        "failed":     "#ef4444",
    }

    rows = ""
    for l in leads:
        color = status_colors.get(l.status, "#6b7280")
        drive = f'<a href="{l.drive_url}" target="_blank">View PDF</a>' if l.drive_url else "—"
        rows += f"""
        <tr>
          <td>{l.id}</td>
          <td>{l.name}</td>
          <td>{l.email}</td>
          <td>{l.company}</td>
          <td>{l.industry}</td>
          <td><span style="background:{color};color:white;padding:3px 10px;
              border-radius:20px;font-size:12px;font-weight:600;">{l.status}</span></td>
          <td>{l.created_at.strftime('%Y-%m-%d %H:%M')}</td>
          <td>{drive}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Lead Pipeline — Admin</title>
      <meta charset="UTF-8"/>
      <style>
        body {{ font-family:-apple-system,sans-serif; padding:32px; color:#111; }}
        h1   {{ font-size:22px; margin-bottom:4px; }}
        p    {{ color:#6b7280; margin-bottom:24px; font-size:14px; }}
        table {{ width:100%; border-collapse:collapse; font-size:14px; }}
        th   {{ text-align:left; padding:10px 12px; background:#f3f4f6;
                border-bottom:2px solid #e5e7eb; font-weight:600; }}
        td   {{ padding:10px 12px; border-bottom:1px solid #f3f4f6; }}
        tr:hover td {{ background:#fafafa; }}
        a    {{ color:#4f46e5; text-decoration:none; }}
      </style>
    </head>
    <body>
      <h1>Lead Pipeline Dashboard</h1>
      <p>{len(leads)} lead(s) total — auto-refreshes every 10 seconds</p>
      <table>
        <thead><tr>
          <th>#</th><th>Name</th><th>Email</th><th>Company</th>
          <th>Industry</th><th>Status</th><th>Submitted</th><th>Report</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <script>setTimeout(()=>location.reload(), 10000);</script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ── GET /health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
