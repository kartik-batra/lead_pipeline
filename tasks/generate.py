"""
tasks/generate.py

Two-pass report generation with Groq llama-3.3-70b-versatile:
  Pass 1 — Analytical pass: extract structured insights as JSON
  Pass 2 — Writing pass:    produce the full markdown report using those insights
"""

import json
import re
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, YOUR_COMPANY_NAME

client = Groq(api_key=GROQ_API_KEY)


# ── System prompts ─────────────────────────────────────────────────────────────

ANALYST_SYSTEM = """
You are a senior business intelligence analyst.
Your job is to read raw company data and extract clean, structured insights.
You respond ONLY with valid JSON — no preamble, no markdown fences, no explanation.
Every field must be specific to the company provided. Never write generic filler.
If data is missing for a field, write a one-sentence honest note, not a placeholder.
"""

WRITER_SYSTEM = f"""
You are a senior business development consultant 

Your prospect audit reports are known for three qualities:
- Hyper-specificity: every sentence references something real about this company.
- Commercial sharpness: every observation connects to a business outcome.
- Elegant brevity: you write like a McKinsey partner, not a Wikipedia editor.

Rules:
- Never use filler phrases: "it is worth noting", "in today's landscape", "in conclusion".
- Never write a sentence that could apply to any company — every line must be earned.
- If data is thin, say so in one sentence and move on.
- Tone: confident, consultative, peer-to-peer. Not salesy. Not sycophantic.
"""


# ── Context builder ────────────────────────────────────────────────────────────

def _build_raw_context(lead: dict, enriched: dict) -> str:
    return f"""
LEAD INFORMATION
----------------
Name:          {lead['name']}
Email:         {lead['email']}
Company:       {lead['company']}
Website:       {lead['website']}
Industry:      {lead['industry']}
Pain points (self-reported): {lead['pain_points']}

ENRICHED DATA
-------------
Page title:        {enriched.get('page_title', 'N/A')}
Meta description:  {enriched.get('meta_description', 'N/A')}
About text:        {enriched.get('about_text', 'N/A')}
Wikipedia summary: {enriched.get('wiki_summary', 'N/A')}
Founded:           {enriched.get('founded', 'N/A')}
HQ:                {enriched.get('hq', 'N/A')}
Tech stack:        {enriched.get('tech_stack', 'N/A')}
Recent news:       {enriched.get('news_headlines', 'N/A')}
Competitor signals:{enriched.get('competitors', 'N/A')}
Funding signals:   {enriched.get('funding_signals', 'N/A')}
""".strip()


# ── Pass 1: Analytical extraction ─────────────────────────────────────────────

ANALYST_PROMPT_TEMPLATE = """
Analyse this company data and return a JSON object with exactly these keys:

{{
  "business_model": "How they make money — specific, 2-3 sentences",
  "growth_stage":   "Early / Growth / Scale / Enterprise — with evidence",
  "top_pain":       "The single most acute business pain, linking their self-report to what you observe",
  "hidden_gap":     "A gap they probably haven't articulated — inferred from tech stack or news",
  "best_hook":      "The single strongest opening angle for a first conversation",
  "avoid":          "What NOT to lead with — why it would fall flat for this specific company",
  "competitor_intel": "1-2 sentences on what their competitors do better right now",
  "opportunity":    "How {company_name}'s service maps to their top pain — be specific",
  "next_steps":     ["step 1", "step 2", "step 3"]
}}

RAW DATA:
{raw_context}
"""

def _run_analyst_pass(lead: dict, enriched: dict) -> dict:
    raw_context = _build_raw_context(lead, enriched)
    prompt = ANALYST_PROMPT_TEMPLATE.format(
        company_name = YOUR_COMPANY_NAME,
        raw_context=raw_context,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": ANALYST_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1000,
        temperature=0.2,   # low temperature for consistent structured output
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if model wrapped anyway
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Graceful fallback — return the raw text in a dict
        return {"raw_analysis": raw}


# ── Pass 2: Report writing ─────────────────────────────────────────────────────

WRITER_PROMPT_TEMPLATE = """
Write a prospect audit report for {contact_name} at {company_name}.

Use the structured insights below as your analytical backbone.
Every section must reference specific facts about {company_name} — 
no generic statements that could apply to any company.

STRUCTURED INSIGHTS (from analysis pass):
{insights_json}

RAW CONTEXT (for additional specificity):
{raw_context}

---

Generate the report with exactly these sections in markdown:

# {company_name} — Prospect Intelligence Brief

## Executive snapshot
3–4 sentences. Who they are, what they do, what stage they're at, 
their market position. Mention something specific from their website or news.

## Business model & revenue signals
How do they make money? Pricing model signals? Key growth levers?
Reference their tech stack where relevant (e.g. Stripe = payments, 
HubSpot = inbound motion). 2–3 short paragraphs.

## Identified pain points & gaps
Cross-reference self-reported pain with observed signals.
Name 2–3 specific gaps. Format each as:
**[Pain name]:** symptom → likely root cause → business impact.

## Opportunity mapping
For each pain point above, one paragraph on how {your_company} 
addresses it — specifically for this company. Frame in business 
outcomes: time saved, revenue protected, risk reduced.

## Competitive landscape
2–3 competitors. One specific observation per competitor.
What are they doing better right now? Keep it factual.

## Recommended engagement angle
One focused paragraph. Best hook for the first call.
What framing will resonate most? What to avoid.

## Suggested next steps
- [Step 1]
- [Step 2]  
- [Step 3]

---
Length: 650–900 words across all sections.
Format: clean markdown. No nested bullets. No tables. No emoji.
"""

def _run_writer_pass(lead: dict, enriched: dict, insights: dict) -> str:
    raw_context = _build_raw_context(lead, enriched)
    prompt = WRITER_PROMPT_TEMPLATE.format(
        contact_name=lead["name"],
        company_name=lead["company"],
        insights_json=json.dumps(insights, indent=2),
        your_company = YOUR_COMPANY_NAME,
        raw_context=raw_context,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": WRITER_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=2000,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()


# ── Master function ────────────────────────────────────────────────────────────

async def generate_report(lead: dict, enriched: dict) -> str:
    """
    Run both passes and return the final markdown report string.
    Pass 1 extracts structured insights; Pass 2 writes from them.
    Falls back to single-pass if analysis JSON is malformed.
    """
    # Pass 1 — analytical (sync Groq call, fast enough for asyncio)
    insights = _run_analyst_pass(lead, enriched)

    # Pass 2 — writing
    report_markdown = _run_writer_pass(lead, enriched, insights)

    return report_markdown
