# arXiv Daily Digest — Automation Setup

Fully automated pipeline: scrapes arXiv → filters with Claude → generates HTML report → emails you.

## Quick Start (5 minutes)

```bash
# 1. Install dependencies
cd automation/
pip install -r requirements.txt

# 2. Configure
cp config.example.yaml config.yaml
# Edit config.yaml: add your Anthropic API key and email settings

# 3. Test run (no email)
python daily_digest.py --dry-run

# 4. Check the output
open outputs/arxiv-digest-*.html
```

## Schedule It

### Option A: cron (Linux / macOS)

Run every day at 8:00 AM:

```bash
crontab -e
```

Add this line (adjust paths):

```
0 8 * * * cd /path/to/arxiv-daily-digest/automation && /path/to/python daily_digest.py >> /tmp/arxiv-digest.log 2>&1
```

### Option B: launchd (macOS — survives restarts)

Save as `~/Library/LaunchAgents/com.arxiv.digest.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.arxiv.digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/python</string>
        <string>/path/to/arxiv-daily-digest/automation/daily_digest.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/arxiv-digest.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/arxiv-digest-err.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>sk-ant-...</string>
    </dict>
</dict>
</plist>
```

Then:

```bash
launchctl load ~/Library/LaunchAgents/com.arxiv.digest.plist
```

### Option C: GitHub Actions (runs in the cloud — no local machine needed)

Create `.github/workflows/daily-digest.yml` in a private repo:

```yaml
name: arXiv Daily Digest
on:
  schedule:
    - cron: '0 12 * * *'  # 12:00 UTC = 8AM ET / 9PM JST
  workflow_dispatch:        # Manual trigger button

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r automation/requirements.txt

      - name: Run digest
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python automation/daily_digest.py

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: arxiv-digest-${{ github.run_id }}
          path: automation/outputs/*.html
          retention-days: 30
```

Set your secrets in the repo: Settings → Secrets → `ANTHROPIC_API_KEY` and email credentials.

For email delivery via GitHub Actions, add the email config to secrets and write it at runtime:

```yaml
      - name: Write config
        run: |
          cat > automation/config.yaml << EOF
          anthropic_api_key: "${{ secrets.ANTHROPIC_API_KEY }}"
          model: "claude-sonnet-4-20250514"
          email:
            enabled: true
            smtp_host: "smtp.gmail.com"
            smtp_port: 587
            username: "${{ secrets.EMAIL_USER }}"
            password: "${{ secrets.EMAIL_PASSWORD }}"
            from: "${{ secrets.EMAIL_USER }}"
            to: "${{ secrets.EMAIL_TO }}"
          EOF
```

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `anthropic_api_key` | — | Your Anthropic API key (or use `ANTHROPIC_API_KEY` env var) |
| `model` | `claude-sonnet-4-20250514` | Claude model for filtering and summarization |
| `max_per_category` | `80` | Papers to fetch per arXiv category |
| `lookback_days` | `2` | How far back to look (2 handles weekends) |
| `email.enabled` | `true` | Toggle email delivery |
| `email.smtp_host` | `smtp.gmail.com` | SMTP server |
| `email.smtp_port` | `587` | SMTP port (587 for TLS) |
| `email.username` | — | SMTP login |
| `email.password` | — | SMTP password (use App Password for Gmail) |
| `email.to` | — | Recipient email |

## CLI Options

```bash
python daily_digest.py                    # Run for today
python daily_digest.py --date 2026-05-19  # Specific date
python daily_digest.py --dry-run          # Generate HTML only, skip email
python daily_digest.py --max-papers 10    # Override paper limit
```

## Cost Estimate

Each daily run makes roughly 10-15 Claude API calls:
- 1 call for filtering (~2K input tokens, ~500 output)
- 3-7 calls for summaries (~1K input, ~1K output each)
- Total: ~15K-25K tokens/day ≈ $0.05-0.15/day with Sonnet

## Troubleshooting

- **No papers found**: arXiv may batch weekend papers into Monday. Try `--lookback-days 3`.
- **Email not sending**: Gmail requires an App Password (not your regular password). See [Google's guide](https://support.google.com/accounts/answer/185833).
- **Rate limited by arXiv**: The script includes 3-second delays between API calls. If issues persist, reduce `max_per_category`.
- **Claude API errors**: Check your API key and account balance.
