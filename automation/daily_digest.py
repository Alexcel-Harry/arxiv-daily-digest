#!/usr/bin/env python3
"""
arXiv Daily Digest — Fully Automated Pipeline

Scrapes arXiv → filters with Claude API → generates HTML report → emails you.
Schedule with cron/launchd/Task Scheduler for daily execution.

Usage:
    python daily_digest.py                    # Run for today
    python daily_digest.py --date 2026-05-19  # Run for a specific date
    python daily_digest.py --dry-run          # Skip email, just generate HTML
"""

import os
import re
import json
import time
import argparse
import smtplib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional

import yaml
import requests
import feedparser
from anthropic import Anthropic

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("arxiv-digest")

# ── Configuration ────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.yaml"
INTEREST_PROFILE_PATH = SCRIPT_DIR.parent / "references" / "interest-profile.md"
OUTPUT_DIR = SCRIPT_DIR / "outputs"

ARXIV_CATEGORIES = [
    "cs.RO",   # Robotics
    "cs.CV",   # Computer Vision
    "cs.LG",   # Machine Learning
    "cs.CL",   # NLP / Reasoning
    "cs.AI",   # Artificial Intelligence
    "cs.DC",   # Distributed Computing
    "cs.AR",   # Hardware Architecture
    "cs.PF",   # Performance
    "stat.ML", # ML (stats)
]

# arXiv API rate limit: 1 request per 3 seconds
ARXIV_API_DELAY = 3.0


def load_config() -> dict:
    """Load config from config.yaml."""
    if not CONFIG_PATH.exists():
        log.error(f"Config not found at {CONFIG_PATH}. Copy config.example.yaml and fill it in.")
        raise SystemExit(1)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_interest_profile() -> str:
    """Load the interest profile markdown."""
    if INTEREST_PROFILE_PATH.exists():
        return INTEREST_PROFILE_PATH.read_text()
    # Fallback: check if it's next to the script
    alt = SCRIPT_DIR / "interest-profile.md"
    if alt.exists():
        return alt.read_text()
    log.warning("Interest profile not found — using default keywords.")
    return "Robotics, world models, VLMs, RL, AI infrastructure, reasoning models, omni models."


# ── Step 1: Scrape arXiv ─────────────────────────────────────────────────

def fetch_arxiv_papers(categories: list[str], max_per_cat: int = 80) -> list[dict]:
    """
    Fetch recent papers from arXiv API across all categories.
    Uses the arXiv Atom API: https://info.arxiv.org/help/api/basics.html
    """
    all_papers = {}  # keyed by arxiv_id for dedup

    for cat in categories:
        log.info(f"Fetching {cat}...")
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"cat:{cat}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_per_cat,
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"  Failed to fetch {cat}: {e}")
            continue

        feed = feedparser.parse(resp.text)

        for entry in feed.entries:
            arxiv_id = entry.id.split("/abs/")[-1].split("v")[0]
            if arxiv_id in all_papers:
                # Add this category to existing paper
                all_papers[arxiv_id]["categories"].add(cat)
                continue

            # Extract authors
            authors = [a.get("name", "") for a in entry.get("authors", [])]

            # Extract categories
            tags = {t["term"] for t in entry.get("tags", [])}

            all_papers[arxiv_id] = {
                "id": arxiv_id,
                "title": re.sub(r"\s+", " ", entry.title.strip()),
                "abstract": re.sub(r"\s+", " ", entry.summary.strip()),
                "authors": authors,
                "categories": tags,
                "published": entry.get("published", ""),
                "link": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
            }

        log.info(f"  → {len(feed.entries)} entries (total unique: {len(all_papers)})")
        time.sleep(ARXIV_API_DELAY)

    papers = list(all_papers.values())
    # Convert category sets to sorted lists for JSON serialization
    for p in papers:
        p["categories"] = sorted(p["categories"])

    log.info(f"Total unique papers: {len(papers)}")
    return papers


def filter_recent(papers: list[dict], target_date: Optional[str] = None, lookback_days: int = 2) -> list[dict]:
    """Filter to papers published within lookback_days of target_date."""
    if target_date:
        target = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        target = datetime.utcnow()

    cutoff = target - timedelta(days=lookback_days)
    recent = []
    for p in papers:
        try:
            pub = datetime.strptime(p["published"][:10], "%Y-%m-%d")
            if pub >= cutoff:
                recent.append(p)
        except (ValueError, TypeError):
            continue

    log.info(f"Papers within {lookback_days} days: {len(recent)}")
    return recent


# ── Step 2: Filter with Claude API ───────────────────────────────────────

def build_filter_prompt(papers: list[dict], interest_profile: str) -> str:
    """Build a prompt for Claude to select the top papers."""
    paper_list = ""
    for i, p in enumerate(papers):
        paper_list += f"\n[{i}] {p['title']}\n"
        paper_list += f"    Authors: {', '.join(p['authors'][:5])}{'...' if len(p['authors']) > 5 else ''}\n"
        paper_list += f"    Categories: {', '.join(p['categories'])}\n"
        paper_list += f"    Abstract: {p['abstract'][:500]}{'...' if len(p['abstract']) > 500 else ''}\n"

    return f"""You are a research paper curator. Your job is to select the top 3-7 most interesting papers from today's arXiv submissions based on the user's research interest profile.

## Interest Profile
{interest_profile}

## Today's Papers
{paper_list}

## Instructions
1. Score each paper against the interest profile.
2. NOVELTY is the #1 criterion — skip incremental work.
3. Select the top 3-7 papers (fewer if it's a slow day, more if several are excellent).
4. For each selected paper, assign it to ONE field section:
   - "Robotics Learning"
   - "World Models & Embodied AI"
   - "AI Models — Reasoning, Omni & Architectures"
   - "AI Infrastructure" (training systems, serving, post-training RL infra, data engines — always a standalone section)
   - "Preference & Reward Learning"
   - Or another field name if none of the above fits

Respond ONLY with a JSON array. Each element:
{{
  "index": <paper index from the list>,
  "field": "<field section name>",
  "reason": "<one sentence: why this paper is interesting>"
}}

No other text. Just the JSON array."""


def select_papers_with_claude(
    papers: list[dict],
    interest_profile: str,
    client: Anthropic,
    model: str,
) -> list[dict]:
    """Use Claude to select the most interesting papers."""
    log.info("Asking Claude to filter papers...")

    prompt = build_filter_prompt(papers, interest_profile)

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        selections = json.loads(text)
    except json.JSONDecodeError:
        log.error(f"Failed to parse Claude's selection response:\n{text}")
        return []

    # Attach selection metadata to papers
    selected = []
    for sel in selections:
        idx = sel["index"]
        if 0 <= idx < len(papers):
            paper = papers[idx].copy()
            paper["field"] = sel["field"]
            paper["selection_reason"] = sel["reason"]
            selected.append(paper)

    log.info(f"Selected {len(selected)} papers")
    for s in selected:
        log.info(f"  [{s['field']}] {s['title'][:80]}")

    return selected


# ── Step 3: Summarize with Claude API ────────────────────────────────────

def summarize_paper(paper: dict, interest_profile: str, client: Anthropic, model: str) -> dict:
    """Generate a full 5-section academic summary + personalized relevance."""
    log.info(f"  Summarizing: {paper['title'][:60]}...")

    prompt = f"""You are an academic paper summarizer. Summarize this paper using EXACTLY this 5-section structure, then add a personalized section.

## Paper
Title: {paper['title']}
Authors: {', '.join(paper['authors'])}
Categories: {', '.join(paper['categories'])}

Abstract:
{paper['abstract']}

## User's Research Profile (for the "Why This Matters" section)
{interest_profile[:2000]}

## Output Format
Respond with a JSON object containing these keys (all strings, use markdown within strings):
{{
  "core_question": "2-3 sentences on the central research question",
  "innovation_points": "Markdown bulleted list of 3-6 novel contributions",
  "technical_approaches": "1-2 paragraphs on the method, architecture, key equations",
  "results": "1 paragraph on benchmarks, comparisons, quantitative highlights",
  "future_work": "Markdown bulleted list of limitations and next steps",
  "why_matters": "1 paragraph connecting this paper to the user's specific research interests, projects, and ideas"
}}

No other text. Just the JSON object."""

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        summary = json.loads(text)
        paper["summary"] = summary
    except json.JSONDecodeError:
        log.warning(f"  Failed to parse summary for {paper['id']}, using raw text")
        paper["summary"] = {
            "core_question": text[:500],
            "innovation_points": "",
            "technical_approaches": "",
            "results": "",
            "future_work": "",
            "why_matters": "",
        }

    return paper


# ── Step 4: Generate HTML Report ─────────────────────────────────────────

def md_to_html(md: str) -> str:
    """Minimal markdown→HTML: bullets, bold, code."""
    lines = md.strip().split("\n")
    html_lines = []
    in_ul = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            item = stripped[2:]
            item = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", item)
            item = re.sub(r"`(.+?)`", r"<code>\1</code>", item)
            html_lines.append(f"  <li>{item}</li>")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if stripped:
                stripped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
                stripped = re.sub(r"`(.+?)`", r"<code>\1</code>", stripped)
                html_lines.append(f"<p>{stripped}</p>")
    if in_ul:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


FIELD_COLORS = {
    "Robotics Learning": "#2d6a4f",
    "World Models & Embodied AI": "#7b2cbf",
    "AI Models — Reasoning, Omni & Architectures": "#c77d15",
    "AI Infrastructure": "#0f7b6c",
    "Preference & Reward Learning": "#1a6fb5",
}


def generate_html(selected_papers: list[dict], date_str: str) -> str:
    """Generate the full HTML report."""

    # Group by field
    fields: dict[str, list[dict]] = {}
    for p in selected_papers:
        field = p.get("field", "Other")
        fields.setdefault(field, []).append(p)

    # Ensure AI Infrastructure is ordered properly if present
    ordered_fields = []
    priority = ["Robotics Learning", "World Models & Embodied AI",
                 "AI Models — Reasoning, Omni & Architectures",
                 "AI Infrastructure", "Preference & Reward Learning"]
    for pf in priority:
        if pf in fields:
            ordered_fields.append(pf)
    for f in fields:
        if f not in ordered_fields:
            ordered_fields.append(f)

    # Build nav links
    nav_html = ""
    for i, field in enumerate(ordered_fields):
        color = FIELD_COLORS.get(field, "#666")
        nav_html += f'<a href="#field-{i+1}"><span class="field-dot" style="background:{color}"></span>{field}</a>\n'

    # Build field sections
    sections_html = ""
    for i, field in enumerate(ordered_fields):
        color = FIELD_COLORS.get(field, "#666")
        papers = fields[field]

        cards_html = ""
        for j, p in enumerate(papers):
            s = p.get("summary", {})
            cats = "".join(f'<span class="paper-tag">{c}</span>' for c in p["categories"][:4])

            cards_html += f"""
    <div class="paper-card" onclick="this.classList.toggle('open')">
      <div class="paper-header">
        <span class="paper-index">{i+1}.{j+1}</span>
        <div class="paper-title-group">
          <div class="paper-title">{p['title']}</div>
          <div class="paper-authors">{', '.join(p['authors'][:6])}{'...' if len(p['authors']) > 6 else ''}</div>
          <div class="paper-tags">{cats}</div>
        </div>
        <span class="expand-icon">▾</span>
      </div>
      <div class="paper-body">
        <h3>1. Core Question</h3>
        {md_to_html(s.get('core_question', 'N/A'))}

        <h3>2. Innovation Points</h3>
        {md_to_html(s.get('innovation_points', 'N/A'))}

        <h3>3. Technical Approaches</h3>
        {md_to_html(s.get('technical_approaches', 'N/A'))}

        <h3>4. Results Analysis</h3>
        {md_to_html(s.get('results', 'N/A'))}

        <h3>5. Future Work / Limitations</h3>
        {md_to_html(s.get('future_work', 'N/A'))}

        <div class="why-matters">
          <strong>🔗 Why This Paper Matters to You</strong>
          {md_to_html(s.get('why_matters', ''))}
        </div>

        <div class="paper-links">
          <a href="{p['link']}" target="_blank">📄 arXiv</a>
          <a href="{p['pdf']}" target="_blank">PDF</a>
        </div>
      </div>
    </div>"""

        sections_html += f"""
  <section class="field-section" id="field-{i+1}">
    <div class="field-header">
      <span class="field-number">{i+1}</span>
      <span class="field-name">{field}</span>
      <span class="field-bar" style="background:{color}"></span>
    </div>
    {cards_html}
  </section>"""

    total_papers = len(selected_papers)
    total_fields = len(ordered_fields)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>arXiv Daily Digest — {date_str}</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,500;0,9..144,700;1,9..144,400&family=Source+Sans+3:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #faf8f4; --bg-card: #ffffff; --text: #1a1a2e; --text-secondary: #5a5a72;
    --accent: #c4553a; --accent-soft: #f0d8d0; --border: #e8e4de;
    --tag-bg: #eef0f7; --tag-text: #3d4a7a; --nav-bg: #1a1a2e; --nav-text: #e8e4de;
  }}
  [data-theme="dark"] {{
    --bg: #121218; --bg-card: #1c1c28; --text: #e8e4de; --text-secondary: #9a98a8;
    --accent: #e07858; --accent-soft: #3d2520; --border: #2e2e3e;
    --tag-bg: #252538; --tag-text: #a8b0d8; --nav-bg: #0a0a12; --nav-text: #c8c4be;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Source Sans 3', -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.65; transition: background 0.3s, color 0.3s; }}
  header {{ background: var(--nav-bg); color: var(--nav-text); padding: 2.5rem 2rem 2rem; position: relative; }}
  header .container {{ max-width: 900px; margin: 0 auto; }}
  header h1 {{ font-family: 'Fraunces', serif; font-weight: 700; font-size: 2.2rem; letter-spacing: -0.02em; margin-bottom: 0.25rem; }}
  header .date {{ font-size: 1rem; opacity: 0.7; font-weight: 300; }}
  header .stats {{ margin-top: 1rem; font-size: 0.88rem; opacity: 0.6; }}
  .theme-toggle {{ position: absolute; top: 1.5rem; right: 2rem; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: var(--nav-text); padding: 0.4rem 0.8rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-family: inherit; }}
  .theme-toggle:hover {{ background: rgba(255,255,255,0.18); }}
  nav {{ background: var(--bg-card); border-bottom: 1px solid var(--border); padding: 0.8rem 2rem; position: sticky; top: 0; z-index: 100; backdrop-filter: blur(12px); }}
  nav .container {{ max-width: 900px; margin: 0 auto; display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: center; }}
  nav a {{ text-decoration: none; font-size: 0.85rem; font-weight: 500; padding: 0.3rem 0.7rem; border-radius: 4px; transition: background 0.2s; color: var(--text-secondary); }}
  nav a:hover {{ background: var(--tag-bg); color: var(--text); }}
  nav .field-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }}
  main {{ max-width: 900px; margin: 0 auto; padding: 2rem; }}
  .field-section {{ margin-bottom: 3rem; }}
  .field-header {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; padding-bottom: 0.6rem; border-bottom: 2px solid var(--border); }}
  .field-number {{ font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.6rem; opacity: 0.25; min-width: 2rem; }}
  .field-name {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.35rem; letter-spacing: -0.01em; }}
  .field-bar {{ height: 3px; width: 40px; border-radius: 2px; margin-left: auto; }}
  .paper-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 1.25rem; overflow: hidden; transition: box-shadow 0.2s, border-color 0.2s; }}
  .paper-card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.06); border-color: var(--accent); }}
  .paper-header {{ padding: 1.25rem 1.5rem; cursor: pointer; display: flex; align-items: flex-start; gap: 1rem; user-select: none; }}
  .paper-index {{ font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.3rem; flex-shrink: 0; }}
  .paper-title-group {{ flex: 1; }}
  .paper-title {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 1.12rem; line-height: 1.4; margin-bottom: 0.4rem; }}
  .paper-authors {{ font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.5rem; }}
  .paper-tags {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
  .paper-tag {{ font-size: 0.72rem; font-weight: 500; background: var(--tag-bg); color: var(--tag-text); padding: 0.15rem 0.5rem; border-radius: 3px; }}
  .expand-icon {{ font-size: 1.2rem; color: var(--text-secondary); transition: transform 0.3s; flex-shrink: 0; margin-top: 0.2rem; }}
  .paper-card.open .expand-icon {{ transform: rotate(180deg); }}
  .paper-body {{ display: none; padding: 0 1.5rem 1.5rem; padding-left: calc(1.5rem + 2.5rem); }}
  .paper-card.open .paper-body {{ display: block; }}
  .paper-body h3 {{ font-family: 'Fraunces', serif; font-weight: 500; font-size: 0.95rem; margin-top: 1.2rem; margin-bottom: 0.5rem; color: var(--accent); }}
  .paper-body h3:first-child {{ margin-top: 0; }}
  .paper-body p {{ font-size: 0.9rem; line-height: 1.7; margin-bottom: 0.6rem; }}
  .paper-body ul {{ margin: 0.3rem 0 0.8rem 1.2rem; font-size: 0.9rem; }}
  .paper-body li {{ margin-bottom: 0.3rem; line-height: 1.55; }}
  .paper-body .why-matters {{ background: var(--accent-soft); border-left: 3px solid var(--accent); padding: 0.9rem 1rem; border-radius: 0 6px 6px 0; margin-top: 1rem; font-size: 0.88rem; line-height: 1.65; }}
  .paper-body .why-matters strong {{ display: block; margin-bottom: 0.3rem; color: var(--accent); font-family: 'Fraunces', serif; }}
  .paper-links {{ display: flex; gap: 0.6rem; margin-top: 1rem; }}
  .paper-links a {{ font-size: 0.82rem; font-weight: 500; text-decoration: none; color: var(--accent); border: 1px solid var(--accent); padding: 0.3rem 0.7rem; border-radius: 5px; transition: background 0.2s, color 0.2s; }}
  .paper-links a:hover {{ background: var(--accent); color: #fff; }}
  footer {{ max-width: 900px; margin: 0 auto; padding: 2rem; text-align: center; font-size: 0.8rem; color: var(--text-secondary); border-top: 1px solid var(--border); }}
  @media print {{ nav, .theme-toggle {{ display: none; }} .paper-body {{ display: block !important; }} .paper-card {{ break-inside: avoid; }} }}
  @media (max-width: 640px) {{ header h1 {{ font-size: 1.6rem; }} main {{ padding: 1rem; }} .paper-header {{ padding: 1rem; }} .paper-body {{ padding: 0 1rem 1rem 1rem; }} }}
</style>
</head>
<body>
<header>
  <button class="theme-toggle" onclick="toggleTheme()">◑ Theme</button>
  <div class="container">
    <h1>arXiv Daily Digest</h1>
    <div class="date">{date_str}</div>
    <div class="stats">Scanned {len(ARXIV_CATEGORIES)} categories · Selected {total_papers} papers across {total_fields} fields</div>
  </div>
</header>
<nav><div class="container">{nav_html}</div></nav>
<main>{sections_html}</main>
<footer>
  <p>Generated by arXiv Daily Digest · Auto-curated with Claude API</p>
  <p>Categories: {', '.join(ARXIV_CATEGORIES)}</p>
</footer>
<script>
function toggleTheme() {{
  const b = document.body;
  b.getAttribute('data-theme') === 'dark' ? b.removeAttribute('data-theme') : b.setAttribute('data-theme', 'dark');
}}
</script>
</body>
</html>"""


# ── Step 5: Email Delivery ───────────────────────────────────────────────

def send_email(html_path: Path, config: dict, date_str: str):
    """Send the HTML report via email."""
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled", False):
        log.info("Email delivery disabled in config.")
        return

    smtp_host = email_cfg["smtp_host"]
    smtp_port = email_cfg.get("smtp_port", 587)
    username = email_cfg["username"]
    password = email_cfg["password"]
    from_addr = email_cfg.get("from", username)
    to_addr = email_cfg["to"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📚 arXiv Digest — {date_str}"
    msg["From"] = from_addr
    msg["To"] = to_addr

    # Plain text fallback
    msg.attach(MIMEText(f"Your arXiv daily digest for {date_str} is attached.", "plain"))

    # HTML body (inline)
    html_content = html_path.read_text()
    msg.attach(MIMEText(html_content, "html"))

    # Also attach as file
    attachment = MIMEBase("text", "html")
    attachment.set_payload(html_content.encode())
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", f"attachment; filename=arxiv-digest-{date_str}.html")
    msg.attach(attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        log.info(f"Email sent to {to_addr}")
    except Exception as e:
        log.error(f"Email failed: {e}")


# ── Main Pipeline ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="arXiv Daily Digest")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), default: today")
    parser.add_argument("--dry-run", action="store_true", help="Generate HTML only, skip email")
    parser.add_argument("--max-papers", type=int, default=7, help="Max papers to include")
    args = parser.parse_args()

    config = load_config()
    date_str = args.date or datetime.utcnow().strftime("%Y-%m-%d")
    log.info(f"=== arXiv Daily Digest for {date_str} ===")

    # Initialize Claude client
    api_key = config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("No API key found. Set ANTHROPIC_API_KEY or add to config.yaml.")
        raise SystemExit(1)

    client = Anthropic(api_key=api_key)
    model = config.get("model", "claude-sonnet-4-20250514")

    # Load interest profile
    interest_profile = load_interest_profile()

    # Step 1: Scrape
    papers = fetch_arxiv_papers(ARXIV_CATEGORIES, max_per_cat=config.get("max_per_category", 80))
    recent = filter_recent(papers, target_date=args.date, lookback_days=config.get("lookback_days", 2))

    if not recent:
        log.warning("No recent papers found. Exiting.")
        return

    # Step 2: Filter
    selected = select_papers_with_claude(recent, interest_profile, client, model)
    if not selected:
        log.warning("Claude selected no papers. Exiting.")
        return

    # Step 3: Summarize
    log.info("Generating full summaries...")
    for paper in selected:
        summarize_paper(paper, interest_profile, client, model)
        time.sleep(1)  # Rate limiting

    # Step 4: Generate HTML
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = generate_html(selected, date_str)
    html_path = OUTPUT_DIR / f"arxiv-digest-{date_str}.html"
    html_path.write_text(html)
    log.info(f"Report saved: {html_path}")

    # Step 5: Deliver
    if not args.dry_run:
        send_email(html_path, config, date_str)

    log.info("Done!")


if __name__ == "__main__":
    main()
