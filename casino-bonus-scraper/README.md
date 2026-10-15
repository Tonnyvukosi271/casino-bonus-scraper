# BonusAtlas — Casino Bonus Scraper

BonusAtlas turns promotion text from one public casino page into a small, comparable dataset. For three casino names you provide, it extracts the welcome bonus, wagering requirement, and minimum deposit, then displays the results in a static website.

It is deliberately conservative: unsupported values are left blank rather than guessed. This is a screening-assessment project, not a production data service or a recommendation to gamble.

## How it works

```text
Check robots.txt → fetch one page → extract terms with AI or explicit table columns
→ validate values → write casinos.json
→ display the JSON in the website
```

The scraper does not run in the browser. The website only reads `casinos.json`; it never contains or needs your API key.

## Features

- Checks the source host's `robots.txt` before fetching and refuses when access is disallowed or the file cannot be read.
- Uses a descriptive User-Agent, a 15-second request timeout, and one source-page fetch per run.
- Matches casino names in page text and separates passages to reduce mixing offers between casinos.
- Uses the official OpenAI Python SDK in JSON mode to extract three fields.
- Offers a `--no-ai` mode that reads welcome bonuses, wagering, and minimum deposits only from explicitly labeled table columns; it requires no API key.
- Checks extracted numbers against the source passage and changes unsupported values to `null`.
- Validates records before writing; failed or unusable runs leave existing data untouched. Valid output is written atomically.
- Provides a responsive static page with search, refresh, record status, source links, and empty/error states.

## Requirements

- Python 3.10 or newer
- An OpenAI API key for the default language-model extraction mode (not needed with `--no-ai`)
- A public page that you are permitted to access automatically

## Set up

Run these commands from the project directory:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Edit `.env` and provide a source URL and exactly three casino names as they appear on that page. The API key is only required for the default AI mode:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4o-mini
SOURCE_URL=https://example.com/promotions
CASINO_NAMES=Casino A,Casino B,Casino C
```

`.env` is ignored by Git. Keep your API key out of source code, screenshots, and public repositories.

Before choosing a source, read its terms and check `https://<host>/robots.txt`. The scraper also checks robots.txt itself; it refuses when the file disallows access or cannot be read. A `404` is treated as no published robots.txt restrictions. Do not use login-only pages or attempt to bypass CAPTCHAs or other anti-bot controls.

## Run the scraper

```bash
python scraper.py
```

You can also pass the source and casino names directly instead of setting them in `.env`:

```bash
python scraper.py --source-url "https://example.com/promotions" --casinos "Casino A,Casino B,Casino C"
```

Use deterministic extraction without an API key:

```bash
python scraper.py --no-ai --source-url "https://example.com/promotions" --casinos "Casino A,Casino B,Casino C"
```

In this mode the scraper only records values from table columns explicitly labeled for those terms. Other values remain `null`; it does not infer casino-specific terms from general page text. Other options include `--model`, `--user-agent`, and `--output`. Run `python scraper.py --help` for the full list.

Exit codes:

- `0` — all three records are complete.
- `2` — usable data was written, but at least one record is partial, missing, or failed extraction.
- `1` — the run failed or no usable output could be written; an existing data file is preserved.

## View the website

From the project directory, start a local static server:

```bash
python -m http.server 8000
```

Open <http://localhost:8000>. Do not open `index.html` directly with `file://`; browsers block the page's `fetch()` request for `casinos.json`. The page shows “No verified records yet” until a successful scrape writes usable records.

## Data format

`casinos.json` contains dataset metadata and one record per requested casino. Missing or unsupported terms are `null`.

| Field | Description |
|---|---|
| `last_updated` | UTC timestamp for the last successful write, or `null` before the first scrape |
| `source_url` | Source page used for the run |
| `casinos` | Array of records, one per requested name |
| `casino_name` | Casino name as supplied |
| `welcome_bonus` | Welcome offer text, or `null` |
| `wagering_requirement` | Wagering multiplier (for example, `35x`), `No wagering`, or `null` |
| `minimum_deposit` | Minimum deposit text, or `null` |
| `extraction_status` | `complete`, `partial`, `not_found`, or `failed` |
| `notes` | Explanation for dropped values or extraction errors |

Each casino record also includes its own `source_url`. See [`casinos.json`](./casinos.json) for the current dataset.

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

Tests use mocked HTTP and language-model responses; they do not need network access or an API key.

## Publish the static website

GitHub Pages can host the front end, but it cannot run the Python scraper or keep an API key secret.

1. Push the project files to the `main` branch of the GitHub repository. Confirm `.env` is not included.
2. In the repository, open **Settings → Pages**.
3. Choose **Deploy from a branch**, select `main` and `/(root)`, then save. GitHub Pages branch publishing supports only the repository root or `/docs`, not this nested project directory. The repository-root `index.html` redirects visitors to this app.
4. Wait for the Pages deployment to finish. Open `https://<owner>.github.io/<repository>/` and check that the dataset or empty state loads.
5. Run the scraper locally and publish the updated `casinos.json` whenever you want to refresh the displayed data.

## Limitations and responsible use

- A live no-AI extraction has been verified against Casino.com's South African casino bonuses page. Its robots.txt allows the page path; the legacy terms-and-conditions URL redirects to the About page, which includes an affiliate disclosure, and no standalone terms-of-use page was found. No live OpenAI request has been made.
- Only static HTML pages are supported. JavaScript-rendered offers are not fetched.
- Casino matching depends on names appearing in the page text. Unusual page layouts may result in `not_found` or partial records.
- Model output can still misread terms. The number check is a safeguard, not proof of accuracy; verify each offer against the linked operator page.
- In `--no-ai` mode, wagering requirements and minimum deposits are recorded only when the source has corresponding labeled table columns. This source's bonuses table does not provide those casino-specific terms, so those fields remain unavailable.
- Promotion terms can change. Treat the dataset as informational, verify current terms with the operator, and follow local age and gambling laws.

## Troubleshooting

- **`OPENAI_API_KEY is not set`** — copy `.env.example` to `.env` and add your key.
- **`robots.txt disallows...`** or cannot be read — choose another source that permits automated access.
- **`Exactly 3 casino names are required`** — check for exactly three comma-separated names.
- **Website cannot load `casinos.json`** — start `python -m http.server` in this directory and open `http://localhost:8000`.
- **No usable records were written** — check the log output and confirm the source page contains the casino names and promotion terms in its HTML text.
