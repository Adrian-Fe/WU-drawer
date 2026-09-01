# Western Union EUR/ARS Rate Tracker

This repository tracks the live EUR-to-ARS exchange rate from Western Union using a Python + Playwright scraper that runs automatically on GitHub Actions.

## What it does

- Visits the live Western Union EUR to ARS converter page
- Extracts the current FX value
- Appends the timestamped rate to `rates.csv`
- Runs every 6 hours via GitHub Actions
- Can also be triggered manually from the Actions tab

## Files

- `scraper.py` — fetches and records the rate
- `requirements.txt` — Python dependencies
- `.github/workflows/track.yml` — scheduled GitHub Actions workflow
- `rates.csv` — historical rate log

## Local usage

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
python scraper.py
```

## GitHub Actions

The workflow is configured with:

```yaml
cron: '0 */6 * * *'
```

This runs at 00:00, 06:00, 12:00, and 18:00 UTC.

What happens in GitHub Actions

The workflow:

installs Python + Playwright
launches headless Chromium
scrapes the live EUR/ARS rate
appends the result to rates.csv
commits and pushes the updated CSV back to the repository