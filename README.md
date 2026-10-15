# BonusAtlas – Casino Bonus Scraper

A small Python project that checks a public casino promotions page, extracts the relevant promo text for three named casinos, validates the data with an OpenAI-powered extraction step, and saves the result as a structured JSON dataset for a static front-end display.

This project is designed to solve one specific problem: comparing casino bonus offers across multiple operators without inventing values that are not actually stated in the source text.

## What it does

- Fetches a public source page and confirms the host allows automated access via `robots.txt`
- Uses a polite `User-Agent` and timeout-based requests
- Extracts readable text from the page and isolates the section associated with each casino
- Sends that text to the OpenAI API in JSON mode to extract:
  - `welcome_bonus`
  - `wagering_requirement`
  - `minimum_deposit`
- Rejects unsupported or hallucinated values by checking that numbers appear in the original text
- Writes the data safely to `casinos.json`
- Shows the results in a lightweight static website that reads the JSON and renders it in a table

## Why this project exists

Casino promotion text is messy and inconsistent. Each operator presents offers differently, and many pages mix promotions, eligibility rules, and terms in a single block of text. This scraper tries to normalize that information into a single comparable dataset while staying conservative about what it records.

## Project layout

```text
.
├── README.md
└── casino-bonus-scraper/
    ├── scraper.py
    ├── index.html
    ├── styles.css
    ├── script.js
    ├── casinos.json
    ├── requirements.txt
    ├── .env.example
    ├── tests/
    ├── production-plan.md
    ├── AI_REFLECTION.md
    └── LICENSE
```

The main implementation lives in the nested `casino-bonus-scraper` directory.

## Quick start

```bash
cd casino-bonus-scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then set your environment values in `.env`:

```env
OPENAI_API_KEY=your_key_here
SOURCE_URL=https://example.com/promotions
CASINO_NAMES=Casino A,Casino B,Casino C
OPENAI_MODEL=gpt-4o-mini
```

Run the scraper:

```bash
python scraper.py
```

The scraper saves structured results to `casinos.json`.

## View the website

Serve the project directory locally:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

The page loads `casinos.json` and renders the results as a static table or empty state.

## Output format

The JSON output includes a dataset-level summary plus per-casino records:

```json
{
  "last_updated": "2026-10-15T12:00:00Z",
  "source_url": "https://example.com/promotions",
  "notes": "...",
  "casinos": [
    {
      "casino_name": "Casino A",
      "welcome_bonus": "100% up to $200",
      "wagering_requirement": "35x",
      "minimum_deposit": "$10",
      "source_url": "https://example.com/promotions",
      "extraction_status": "complete",
      "notes": "Extracted from matched source passage"
    }
  ]
}
```

## Safety and constraints

- The scraper refuses to run if the target host disallows it in `robots.txt`
- No secret keys are committed to the repository; `.env` is ignored by Git
- Data is only extracted from a public, permitted source page
- The validation layer avoids empty or invented values by checking numbers against the original text
- The front-end is static HTML/CSS/JavaScript and does not execute Python or hold API keys

## Testing

```bash
python -m unittest discover -s tests -t . -v
```

The test suite exercises parsing and output behavior without requiring network access or a live OpenAI key.

## Notes

This repository is a focused proof-of-concept scraper and dashboard, not a production casino-data platform. It is intentionally conservative: if a value cannot be proven from the source text, it is left as `null` rather than guessed.
