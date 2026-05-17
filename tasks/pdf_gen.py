"""
tasks/pdf_gen.py

Converts markdown report → styled HTML → PDF using xhtml2pdf
"""

import os
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from config import REPORTS_DIR, YOUR_COMPANY_NAME


# ── Markdown → HTML converter (lightweight, no extra deps) ────────────────────

def _md_to_html(md: str) -> str:
    """
    Convert the report markdown to HTML.
    Handles: headings, bold, bullet lists, paragraphs.
    Applies styled callout boxes for pain-point items.
    """
    lines = md.split("\n")
    html_parts = []
    in_ul = False
    in_steps = False

    for line in lines:
        stripped = line.strip()

        # Skip the H1 (already in the template header)
        if stripped.startswith("# "):
            continue

        # H2 section headings
        if stripped.startswith("## "):
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            if in_steps:
                html_parts.append("</ul>")
                in_steps = False
            heading_text = stripped[3:].strip()
            html_parts.append(f"<h2>{heading_text}</h2>")
            continue

        # Bullet points under "Suggested next steps" → styled numbered list
        is_step_section = any(
            "next step" in p.lower()
            for p in html_parts[-3:]
            if "<h2>" in p
        )

        if stripped.startswith("- ") or stripped.startswith("* "):
            item_text = stripped[2:].strip()
            item_text = _inline_format(item_text)

            if "next step" in " ".join(html_parts[-8:]).lower():
                # Numbered step style
                if not in_steps:
                    if in_ul:
                        html_parts.append("</ul>")
                        in_ul = False
                    html_parts.append('<ul class="steps-list">')
                    in_steps = True
                # step_num = html_parts.count('<li>') + 1
                html_parts.append(
                    f'<li>{item_text}</li>'
                )
            else:
                if in_steps:
                    html_parts.append("</ul>")
                    in_steps = False
                if not in_ul:
                    html_parts.append("<ul>")
                    in_ul = True
                html_parts.append(f"<li>{item_text}</li>")
            continue

        # Close lists before paragraphs
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_steps:
            html_parts.append("</ul>")
            in_steps = False

        # Pain point lines: **Label:** text → styled callout box
        pain_match = re.match(r"\*\*([^:]+):\*\*\s*(.*)", stripped)
        if pain_match and len(stripped) > 20:
            label = pain_match.group(1)
            rest  = _inline_format(pain_match.group(2))
            html_parts.append(
                f'<div class="pain-box"><strong>{label}:</strong> {rest}</div>'
            )
            continue

        # Normal paragraph
        if stripped:
            html_parts.append(f"<p>{_inline_format(stripped)}</p>")

    # Close any open lists
    if in_ul:
        html_parts.append("</ul>")
    if in_steps:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_format(text: str) -> str:
    """Apply bold and italic markdown inline."""
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic: *text*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


# ── PDF renderer ──────────────────────────────────────────────────────────────

def render_pdf(report_markdown: str, lead: dict) -> str:
    """
    Render the markdown report to a PDF file.
    Returns the absolute path to the saved PDF.
    """
    # Convert markdown → HTML
    report_html = _md_to_html(report_markdown)

    # Build Jinja2 template context
    now = datetime.utcnow()
    context = {
        "your_company": YOUR_COMPANY_NAME,
        "name":         lead["name"],
        "email":        lead["email"],
        "company":      lead["company"],
        "website":      lead["website"],
        "industry":     lead["industry"],
        "date":         now.strftime("%B %d, %Y"),
        "year":         now.strftime("%Y"),
        "report_html":  report_html,
    }

    # Render HTML template
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")
    rendered_html = template.render(**context)

    # Generate PDF
    safe_company = re.sub(r"[^\w\-]", "_", lead["company"])
    timestamp    = now.strftime("%Y%m%d_%H%M%S")
    filename     = f"{safe_company}_audit_{timestamp}.pdf"
    output_path  = os.path.join(REPORTS_DIR, filename)

    with open(output_path, "wb") as pdf_file:
        result = pisa.CreatePDF(
            src=rendered_html,
            dest=pdf_file,
            path='.'
        )
    
    if result.err:
        raise Exception(f"PDF generation failed for {filename}")
    
    return os.path.abspath(output_path)
