"""
tasks/enrich.py

Three enrichment sources, all free:
  1. Direct website scrape  — httpx + BeautifulSoup4
  2. SerpAPI Google search  — news, competitors, funding signals
  3. Wikipedia REST API     — company overview, founding, size
"""

import httpx
import asyncio
import re
from bs4 import BeautifulSoup
from config import SERPAPI_KEY
from urllib.parse import quote_plus


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean(text: str, max_chars: int = 600) -> str:
    """Strip excess whitespace and truncate."""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] if len(text) > max_chars else text

def _detect_tech_stack(html: str, headers: dict) -> list[str]:
    """Infer tech stack from script tags and response headers."""
    signals = {
        "React":         "react",
        "Vue.js":        "vue",
        "Angular":       "angular",
        "Next.js":       "_next",
        "Nuxt":          "__nuxt",
        "WordPress":     "wp-content",
        "Shopify":       "shopify",
        "HubSpot":       "hubspot",
        "Intercom":      "intercom",
        "Stripe":        "stripe",
        "Segment":       "segment",
        "Google Analytics": "gtag",
        "Hotjar":        "hotjar",
        "Salesforce":    "salesforce",
        "Zendesk":       "zendesk",
    }
    html_lower = html.lower()
    detected = [name for name, sig in signals.items() if sig in html_lower]

    # Check server header
    server = headers.get("server", "")
    if server:
        detected.append(f"Server: {server}")

    powered_by = headers.get("x-powered-by", "")
    if powered_by:
        detected.append(f"Powered by: {powered_by}")

    return detected[:8]  # cap at 8 signals


# ── Source 1: Website scraper ──────────────────────────────────────────────────

async def scrape_website(url: str) -> dict:
    """Scrape the company homepage for about text, meta description, and tech signals."""
    result = {
        "meta_description": "",
        "about_text": "",
        "tech_stack": [],
        "page_title": "",
    }

    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            html = resp.text
            resp_headers = dict(resp.headers)

        soup = BeautifulSoup(html, "html.parser")

        # Page title
        result["page_title"] = _clean(soup.title.string if soup.title else "")

        # Meta description
        meta = soup.find("meta", attrs={"name": "description"}) or \
               soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):
            result["meta_description"] = _clean(meta["content"])

        # About / hero text — grab meaningful paragraphs
        paragraphs = []
        for tag in soup.find_all(["p", "h1", "h2"], limit=40):
            text = tag.get_text(strip=True)
            if len(text) > 40:
                paragraphs.append(text)

        result["about_text"] = _clean(" ".join(paragraphs[:6]))

        # Tech stack detection
        result["tech_stack"] = _detect_tech_stack(html, resp_headers)

        # Also try scraping /about page
        about_url = url.rstrip("/") + "/about"
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                ar = await c.get(about_url, headers=headers)
                if ar.status_code == 200:
                    about_soup = BeautifulSoup(ar.text, "html.parser")
                    about_paras = [
                        p.get_text(strip=True)
                        for p in about_soup.find_all("p")
                        if len(p.get_text(strip=True)) > 50
                    ]
                    if about_paras:
                        result["about_text"] = _clean(
                            result["about_text"] + " " + " ".join(about_paras[:4])
                        )
        except Exception:
            pass  # /about doesn't exist — fine

    except Exception as e:
        result["error"] = str(e)

    return result


# ── Source 2: SerpAPI ─────────────────────────────────────────────────────────

async def search_serpapi(company: str) -> dict:
    """Run two searches: recent news and competitor discovery."""
    result = {"news": [], "competitors": [], "funding": ""}

    if not SERPAPI_KEY:
        return result

    async with httpx.AsyncClient(timeout=15) as client:

        # Search 1: recent news
        try:
            news_q = quote_plus(f"{company} company news 2024 2025")
            r = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": news_q,
                    "api_key": SERPAPI_KEY,
                    "num": 5,
                    "tbm": "nws",
                }
            )
            data = r.json()
            news_results = data.get("news_results", [])
            result["news"] = [
                f"{item.get('title', '')} ({item.get('date', '')})"
                for item in news_results[:4]
            ]
        except Exception:
            pass

        # Search 2: competitors
        try:
            comp_q = quote_plus(f"{company} competitors alternatives")
            r2 = await client.get(
                "https://serpapi.com/search",
                params={
                    "q": comp_q,
                    "api_key": SERPAPI_KEY,
                    "num": 5,
                }
            )
            data2 = r2.json()
            # Pull competitor names from organic snippets
            snippets = []
            for item in data2.get("organic_results", [])[:5]:
                snippet = item.get("snippet", "")
                if snippet:
                    snippets.append(snippet)
            result["competitors"] = _clean(" | ".join(snippets), 500)
        except Exception:
            pass

        # Search 3: funding / size signals
        try:
            fund_q = quote_plus(f"{company} funding raised employees size")
            r3 = await client.get(
                "https://serpapi.com/search",
                params={"q": fund_q, "api_key": SERPAPI_KEY, "num": 3}
            )
            data3 = r3.json()
            snippets3 = [
                item.get("snippet", "")
                for item in data3.get("organic_results", [])[:3]
                if item.get("snippet")
            ]
            result["funding"] = _clean(" ".join(snippets3), 400)
        except Exception:
            pass

    return result


# ── Source 3: Wikipedia REST API ──────────────────────────────────────────────

async def search_wikipedia(company: str) -> dict:
    """Search Wikipedia for company overview — completely free, no key."""
    result = {"summary": "", "founded": "", "hq": ""}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: search for the page
            search_url = "https://en.wikipedia.org/w/api.php"
            sr = await client.get(search_url, params={
                "action": "query",
                "list": "search",
                "srsearch": company,
                "format": "json",
                "srlimit": 1,
            })
            pages = sr.json().get("query", {}).get("search", [])
            if not pages:
                return result

            page_title = pages[0]["title"]

            # Step 2: get the extract (plain text summary)
            er = await client.get(search_url, params={
                "action": "query",
                "titles": page_title,
                "prop": "extracts",
                "exintro": True,
                "explaintext": True,
                "format": "json",
            })
            pages_data = er.json().get("query", {}).get("pages", {})
            page = next(iter(pages_data.values()))
            extract = page.get("extract", "")

            result["summary"] = _clean(extract, 700)

            # Extract founding year
            year_match = re.search(r"founded in (\d{4})|established in (\d{4})", extract, re.I)
            if year_match:
                result["founded"] = year_match.group(1) or year_match.group(2)

            # Extract HQ
            hq_match = re.search(r"headquartered in ([A-Za-z\s,]+)\.", extract)
            if hq_match:
                result["hq"] = hq_match.group(1).strip()

    except Exception:
        pass

    return result


# ── Master enrichment function ─────────────────────────────────────────────────

async def enrich_company(lead: dict) -> dict:
    """
    Run all three enrichment sources concurrently.
    Returns a single flat dict consumed by the report generator.
    """
    website_data, serp_data, wiki_data = await asyncio.gather(
        scrape_website(lead["website"]),
        search_serpapi(lead["company"]),
        search_wikipedia(lead["company"]),
    )

    return {
        # Website
        "page_title":       website_data.get("page_title", ""),
        "meta_description": website_data.get("meta_description", ""),
        "about_text":       website_data.get("about_text", ""),
        "tech_stack":       ", ".join(website_data.get("tech_stack", [])) or "Not detected",

        # SerpAPI
        "news_headlines":   " | ".join(serp_data.get("news", [])) or "No recent news found",
        "competitors":      serp_data.get("competitors", "Not found"),
        "funding_signals":  serp_data.get("funding", "Not found"),

        # Wikipedia
        "wiki_summary":     wiki_data.get("summary", ""),
        "founded":          wiki_data.get("founded", "Unknown"),
        "hq":               wiki_data.get("hq", "Unknown"),
    }
