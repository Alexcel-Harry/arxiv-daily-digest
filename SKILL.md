---
name: arxiv-daily-digest
description: >
  Scrape arXiv for new papers and generate a daily digest report as a polished HTML page.
  Use this skill whenever the user asks for their daily paper digest, arXiv update, new papers,
  paper scraping, research digest, or anything related to checking what's new on arXiv.
  Also trigger on phrases like "what's new on arXiv", "daily papers", "paper report",
  "any interesting papers today", "arXiv digest", "scrape arXiv", "paper roundup",
  "research update", or "what papers came out". Even casual phrasing like "papers?"
  or "anything good on arXiv?" should trigger this skill. This skill is intended as a
  daily routine — trigger it even if the user just says "morning report" or "daily routine"
  in research contexts.
---

# arXiv Daily Digest Skill

Generate a curated daily report of the most interesting new arXiv papers, tailored to the user's research interests. Output is a polished HTML page with full academic summaries.

## Quick Reference

- **Target**: 3–5 best papers per day (quality over quantity; may go up to 6–7 on heavy days given the broad scope across robotics, AI models, and infrastructure)
- **Output**: HTML file saved to `/mnt/user-data/outputs/`
- **Depth**: Full 5-section academic summary per paper (uses the `academic-paper-summary` skill template)
- **Key value**: Novelty filtering — only papers with genuinely new ideas

---

## Step 0: Load the Interest Profile

Before doing anything, read the interest profile:

```
references/interest-profile.md
```

This file contains the user's detailed research interests, organized by priority. Use it as the primary filter for deciding which papers are "interesting." The profile is maintained and can be updated by the user over time.

---

## Step 1: Scrape arXiv New Submissions

Fetch new submissions from these arXiv categories (in priority order):

| Category | Covers |
|----------|--------|
| `cs.RO`  | Robotics |
| `cs.CV`  | Computer Vision |
| `cs.LG`  | Machine Learning |
| `cs.CL`  | Computation and Language (NLP, reasoning models, RLHF) |
| `cs.AI`  | Artificial Intelligence |
| `cs.DC`  | Distributed Computing (training/serving systems) |
| `cs.AR`  | Hardware Architecture (AI accelerators, edge compute) |
| `cs.PF`  | Performance (systems optimization) |
| `stat.ML` | Machine Learning (stats side) |

**How to fetch:**

Use `web_fetch` on the arXiv new-submissions pages. The URL pattern is:

```
https://arxiv.org/list/{category}/new
```

For example: `https://arxiv.org/list/cs.RO/new`

Each page lists that day's new submissions with titles and author lists. Extract:
- Paper title
- Authors
- arXiv ID (e.g., `2505.12345`)
- Abstract link: `https://arxiv.org/abs/{id}`

**Important**: Papers appear on multiple category pages (cross-listed). Deduplicate by arXiv ID.

**Rate limiting**: Fetch categories sequentially, not in parallel. Be respectful of arXiv servers.

---

## Step 2: First-Pass Filtering (Title + Abstract Scan)

From the collected papers (often 100+ per day across all categories), do a quick relevance scan:

1. **Title scan**: Immediately flag papers whose titles contain keywords strongly aligned with the interest profile (e.g., "world model", "humanoid", "reward", "VLM", "diffusion policy", "sim-to-real", "embodied", "3D scene", "robot learning", "reasoning", "chain-of-thought", "test-time compute", "process reward", "omni", "any-to-any", "multimodal", "unified model", "distributed training", "KV-cache", "speculative decoding", "serving system", "RLHF", "post-training", "data engine", "fleet", "inference optimization").

2. **Abstract fetch**: For flagged papers (and any with ambiguous titles that could be relevant), use `web_fetch` on `https://arxiv.org/abs/{id}` to read the abstract.

3. **Relevance scoring**: Mentally score each paper against the interest profile:
   - Does it fall into a primary interest area? (must for inclusion)
   - Is it **novel**? (the user cares deeply about this — skip incremental work)
   - Does it introduce a new formulation, architecture, or cross-domain insight?
   - Is it from a notable lab or venue?
   - For **AI infrastructure** papers: systems contributions count as novelty even without new ML algorithms. A new training system, serving optimization, or RL pipeline is interesting on its own merits.
   - For **reasoning model** papers: include if they introduce new training methods (not just prompting tricks), novel RL post-training approaches, or systems for reasoning at scale.
   - For **omni model** papers: include if they present genuinely unified architectures (not just "we fine-tuned a VLM on audio too").

4. **Select top 3–5 papers**. When in doubt, prefer fewer, higher-quality picks over more borderline ones.

---

## Step 3: Full Paper Summarization

For each selected paper, generate a full academic summary following the `academic-paper-summary` skill's 5-section template:

### Reading the Paper

Use `web_fetch` on the arXiv HTML version when available:
```
https://arxiv.org/html/{id}
```
If HTML is not available, fall back to the abstract page. For very important papers, fetch the PDF via:
```
https://arxiv.org/pdf/{id}
```

### Summary Sections (per the academic-paper-summary skill)

1. **Core Question / Core Problem** (2–3 sentences)
2. **Innovation Points** (3–6 bullet points)
3. **Technical Approaches** (most detailed section — architecture, algorithm, key equations)
4. **Results Analysis** (benchmarks, baselines, quantitative highlights)
5. **Future Work / Limitations**

### Additional Section: "Why This Paper Matters to You"

After the standard 5 sections, add a personalized paragraph:
- Connect the paper to the user's specific research (backflip project, VLM-as-critic idea, world model interests, infra work, etc.)
- Identify actionable insights — what could the user apply or build on?
- Note connections to other papers the user has read or discussed

---

## Step 4: Check for Missed Papers from Earlier Days

Before generating the report, consider:
- Were there papers from the previous 1–2 days that were missed? (The user may mention this, or you can check by scanning `https://arxiv.org/list/{category}/pastweek` if the user hasn't run the digest recently.)
- If the user says "I haven't checked in X days", scan those days as well.
- Missed papers go in a separate section at the end of the report.

---

## Step 5: Generate the HTML Report

Create a polished, readable HTML page. The report structure is:

```
📅 arXiv Daily Digest — {Date}

(1) Field 1 (e.g., "Robotics Learning")
    (1.1) Paper Title
          - Full 5-section summary
          - "Why this matters to you" paragraph
          - Link to arXiv
    (1.2) Paper Title
          ...

(2) Field 2 (e.g., "World Models & Video")
    (2.1) Paper Title
          ...

(3) Field 3 (e.g., "AI Models — Reasoning, Omni & Architectures")
    (3.1) Paper Title
          ...

(4) AI Infrastructure (always a standalone section — covers LLM systems, 
    post-training RL infra, serving, training systems, data engines, etc.)
    (4.1) Paper Title
          ...

...

(n) Field N
    ...

(n+1) Missed from Earlier Days (if any)
    (n+1.1) Paper Title [originally published: date]
            ...
```

**Field assignment notes:**
- "AI Infrastructure" is always its own section — never merge infra papers into "Robotics Learning" or "AI Models." Systems papers (distributed training, KV-cache optimization, RL post-training pipelines, data curation systems, fleet-scale serving) belong here even if they lack novel ML algorithms.
- Reasoning model papers (o1-style RL post-training, process reward models, test-time compute) go under "AI Models" unless they are primarily about the systems/infra side, in which case they go under "AI Infrastructure."
- Omni-model papers (unified multimodal architectures, any-to-any generation) go under "AI Models."
- Papers that touch both robotics and infrastructure (e.g., fleet-scale robot learning systems) can appear in either section — choose based on the paper's primary contribution.

### HTML Design Guidelines

Read the `frontend-design` skill (at `/mnt/skills/public/frontend-design/SKILL.md`) before generating the HTML to ensure high design quality. Key requirements:

- **Clean, readable typography**: Use a distinctive serif or editorial font for headings, a readable sans-serif for body text. Load from Google Fonts.
- **Color scheme**: Academic/editorial tone — think dark navy, warm cream/paper, accent color for highlights. NOT generic purple gradients.
- **Layout**: Single-column reading layout with generous margins. Collapsible sections for each paper (so the user can scan titles first, then expand for full summaries).
- **Navigation**: Sticky sidebar or top nav with field names for quick jumping.
- **Paper cards**: Each paper should be a distinct card with clear visual hierarchy: title → innovation points → expandable full summary.
- **Links**: Each paper links to its arXiv page. Include a "📄 PDF" link as well.
- **Responsive**: Should be readable on both desktop and mobile.
- **Dark/light mode toggle**: Nice to have.
- **Print-friendly**: The page should print cleanly if the user wants a hard copy.

### File Output

Save the HTML file to:
```
/mnt/user-data/outputs/arxiv-digest-{YYYY-MM-DD}.html
```

Then use `present_files` to share it with the user.

---

## Step 6: Post-Report Summary

After presenting the HTML file, give a brief conversational summary in chat:
- "Today I found X papers across Y fields. Highlights: [one-liner per paper]."
- Flag any paper that seems especially aligned with the user's current projects.
- If a day had no interesting papers in any category, say so honestly rather than padding with mediocre picks.

---

## Edge Cases & Notes

- **Weekend / holiday submissions**: arXiv batches weekend submissions into Monday's listing. The skill should handle this gracefully (the Monday report may be larger).
- **No interesting papers**: It's fine to report "nothing stood out today." Don't force-include papers that aren't genuinely interesting.
- **User asks for a specific date range**: Adjust the scraping to cover `https://arxiv.org/list/{category}/YYMM` or use the `pastweek` listing.
- **User wants to adjust interests**: Point them to `references/interest-profile.md` and offer to update it.
- **Cross-listed papers**: A paper in both cs.CV and cs.RO should appear under whichever field is the best fit, not duplicated.
- **Rate limiting**: If arXiv returns errors, wait and retry. Don't hammer the server.
