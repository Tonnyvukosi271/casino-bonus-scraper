# BonusAtlas – Casino Bonus Scraper

A small Python project that checks a public casino promotions page and saves supported offer terms as JSON for a static front end. Extraction can use an OpenAI-powered mode or a deterministic no-API mode that reads explicitly labeled table columns.

This project is designed to solve one specific problem: comparing casino bonus offers across multiple operators without inventing values that are not actually stated in the source text.

## What it does

- Fetches a public source page and confirms the host allows automated access via `robots.txt`
- Uses a polite `User-Agent` and timeout-based requests
- Extracts readable text from the page and isolates the section associated with each casino
- Extracts these fields using AI or explicit source-table labels:
  - `welcome_bonus`
  - `wagering_requirement`
  - `minimum_deposit`
- In AI mode, rejects unsupported values when extracted numbers do not appear in the matched source text
- Leaves terms blank when the source does not state them
- Writes the data safely to `casinos.json`
- Shows the results in a lightweight static website that reads the JSON and renders it in a table

## Why this project exists

Casino promotion text is messy and inconsistent. Each operator presents offers differently, and many pages mix promotions, eligibility rules, and terms in a single block of text. This scraper tries to normalize that information into a single comparable dataset while staying conservative about what it records.

## Project layout

```text
.
├── README.md
├── .github/
│   └── workflows/
│       └── tests.yml
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
    ├── SUBMISSION.md
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

For AI-assisted extraction, set your environment values in `.env`:

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

Without an API key, use table-only extraction:

```bash
python scraper.py --no-ai --source-url "https://example.com/promotions" --casinos "Casino A,Casino B,Casino C"
```

The scraper saves structured results to `casinos.json`. Check the source's terms and `robots.txt` before scraping; the scraper enforces robots rules but cannot determine whether your use is otherwise permitted.

## View the website

Serve the project directory locally:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

The page loads `casinos.json` and renders the results as a static table or empty state. The repository-root `index.html` redirects visitors to the app in `casino-bonus-scraper/`.

## Publish with GitHub Pages

1. Push the project to the `main` branch and confirm `.env` is not committed.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select branch `main` and folder `/(root)`, then save. GitHub Pages only offers the repository root or `/docs`; it cannot publish directly from the nested `casino-bonus-scraper/` folder. The root `index.html` forwards visitors to the app.
5. Wait for the Pages deployment to finish, then open <https://tonnyvukosi271.github.io/casino-bonus-scraper/> and confirm the app loads.

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

The test suite exercises parsing and output behavior without requiring network access or an OpenAI key.

## Live dataset

The deployed example uses [Casino.com's South African bonuses page](https://www.casino.com/zar/bonuses/). The page states welcome bonuses for Jackpot City, YesPlay, and Jabulabets but does not state their casino-specific wagering requirements or minimum deposits. Those fields are intentionally left empty. The deployed copy is available at <https://tonnyvukosi271.github.io/casino-bonus-scraper/>.

The public GitHub Pages URL and dataset returned HTTP 200 when checked on 2026-10-15. This verifies that the site is publicly reachable from the check environment, not that it has been tested from a South African network or that any listed casino accepts South African residents. The source market is South Africa; verify operator availability, licensing, and offer eligibility directly.

## Notes

This repository is a focused proof-of-concept scraper and dashboard, not a production casino-data platform. Offers can change, source terms may restrict reuse, and automated extraction can be wrong; verify current terms with each operator and follow local laws. If a value cannot be supported by the source text, it is left as `null` rather than guessed.
