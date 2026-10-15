#!/usr/bin/env python3
"""BonusAtlas scraper.

Pipeline: check robots.txt -> fetch page -> extract text -> find each casino's
passage -> language model structures it -> validate -> write casinos.json safely.

Run:  python scraper.py --source-url https://example.com/page --casinos "A,B,C"
(or put SOURCE_URL / CASINO_NAMES / OPENAI_API_KEY in a .env file).
"""
import argparse
import json
import logging
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("bonusatlas")

DEFAULT_OUTPUT = "casinos.json"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_USER_AGENT = "BonusAtlasBot/1.0 (educational screening project; polite, low-rate)"
TIMEOUT_SECONDS = 15
SNIPPET_CHARS = 700
FIELDS = ("welcome_bonus", "wagering_requirement", "minimum_deposit")
STATUSES = ("complete", "partial", "not_found", "failed")
UNKNOWN_WORDS = {"", "unknown", "n/a", "na", "null", "none", "not specified", "not stated"}
KEYWORDS = ("bonus", "wager", "deposit", "free spins", "£", "$", "€")

SYSTEM_PROMPT = (
    "You extract casino promotion terms from text. Return ONLY a JSON object with exactly "
    "these keys: welcome_bonus, wagering_requirement, minimum_deposit. Each value is a short "
    "string copied or tightly summarised from the text, or null if the text does not state it. "
    "Never guess, never use outside knowledge, never invent numbers. Use null when unsure."
)


class ScraperError(Exception):
    """Base class for expected, user-facing failures."""


class FetchError(ScraperError):
    pass


class RobotsDisallowed(ScraperError):
    pass


class ModelOutputError(ScraperError):
    pass


# ---------- 1. Source checks and fetching ----------

def validate_url(url):
    parts = urlparse(url or "")
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def check_robots(url, user_agent, session=requests):
    """Raise RobotsDisallowed unless robots.txt clearly permits fetching `url`."""
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = session.get(robots_url, headers={"User-Agent": user_agent}, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RobotsDisallowed(f"Could not read {robots_url} ({exc}); refusing to scrape without it.") from exc
    if resp.status_code in (401, 403) or resp.status_code >= 500:
        raise RobotsDisallowed(f"{robots_url} returned HTTP {resp.status_code}; refusing to scrape.")
    if resp.status_code >= 400:  # e.g. 404: no robots.txt means no stated restrictions
        log.info("No robots.txt found (HTTP %s); continuing.", resp.status_code)
        return
    parser = RobotFileParser()
    parser.parse(resp.text.splitlines())
    if not parser.can_fetch(user_agent, url):
        raise RobotsDisallowed(f"robots.txt disallows fetching {url} for this User-Agent.")


def fetch_page(url, user_agent, session=requests):
    """Return page HTML or raise FetchError. No login/CAPTCHA/anti-bot bypassing."""
    try:
        resp = session.get(url, headers={"User-Agent": user_agent}, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise FetchError(f"HTTP error while fetching {url}: {exc}") from exc
    except requests.RequestException as exc:
        raise FetchError(f"Network error while fetching {url}: {exc}") from exc
    return resp.text


# ---------- 2. Text extraction ----------

def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def find_snippets(text, names, chars=SNIPPET_CHARS):
    """Map each casino name to the passage most likely to describe its offer (or None)."""
    lowered = text.lower()
    snippets = {}
    for name in names:
        best, best_score = None, -1
        others = [n.lower() for n in names if n.lower() != name.lower()]
        # Whole-word match so "Alpha" does not match inside "Alphabet".
        for match in re.finditer(rf"(?<!\w){re.escape(name.lower())}(?!\w)", lowered):
            end = match.start() + chars
            for other in others:  # stop at the next casino so offers are not mixed up
                nxt = re.search(rf"(?<!\w){re.escape(other)}(?!\w)", lowered[match.end():])
                if nxt:
                    end = min(end, match.end() + nxt.start())
            passage = text[match.start():end]
            score = sum(passage.lower().count(k) for k in KEYWORDS)
            if score > best_score:
                best, best_score = passage, score
        snippets[name] = best if best_score > 0 else None
    return snippets


# ---------- 3. Language-model structuring and validation ----------

def make_client():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ScraperError("OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ScraperError("The 'openai' package is missing. Run: pip install -r requirements.txt") from exc
    return OpenAI(api_key=api_key)


def call_model(client, model, name, snippet):
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Casino: {name}\n\nText:\n{snippet}"},
        ],
    )
    return resp.choices[0].message.content


def find_wagering_multiplier(text):
    """Return e.g. '35x' for '35x', '35 x', '35×', '35 times', 'x35'; else None."""
    m = re.search(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s*(?:x|×|times)(?![a-z])", text, re.I)
    m = m or re.search(r"(?<![a-z])x\s*(\d{1,3}(?:\.\d+)?)(?!\d)", text, re.I)
    return f"{float(m.group(1)):g}x" if m else None


def numbers_supported(value, source_text):
    """True if every number in `value` also appears in the source text (anti-hallucination)."""
    haystack = source_text.replace(",", "")
    # Whole-number match only: "35" must not be satisfied by "350" or "1.35".
    return all(
        re.search(rf"(?<![\d.]){re.escape(n.replace(',', ''))}(?![\d]|\.\d)", haystack)
        for n in re.findall(r"\d+(?:[.,]\d+)*", value)
    )


def parse_model_output(raw, snippet):
    """Validate model JSON. Return (fields, notes). Raise ModelOutputError if malformed."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ModelOutputError(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict) or any(k not in data for k in FIELDS):
        raise ModelOutputError(f"Model JSON must be an object with keys {FIELDS}.")
    fields, notes = {}, []
    for key in FIELDS:
        value = data[key]
        if value is not None and not isinstance(value, str):
            raise ModelOutputError(f"Field '{key}' must be a string or null.")
        value = (value or "").strip()
        if value.lower() in UNKNOWN_WORDS:
            fields[key] = None
            continue
        if key == "wagering_requirement":
            if re.search(r"no wagering|wager[- ]free", value, re.I):
                value = "No wagering"
            else:
                value = find_wagering_multiplier(value)
                if value is None:
                    notes.append("wagering_requirement was not a recognisable multiplier; set to null.")
                    fields[key] = None
                    continue
        if not numbers_supported(value, snippet):
            notes.append(f"{key} was not supported by the source text; set to null.")
            fields[key] = None
            continue
        fields[key] = value
    return fields, notes


# ---------- 4. Records, dataset validation, safe writing ----------

def status_for(fields):
    return "complete" if all(fields.get(k) for k in FIELDS) else "partial"


def build_record(name, source_url, fields=None, status="not_found", notes=""):
    fields = fields or {}
    return {
        "casino_name": name,
        "welcome_bonus": fields.get("welcome_bonus"),
        "wagering_requirement": fields.get("wagering_requirement"),
        "minimum_deposit": fields.get("minimum_deposit"),
        "source_url": source_url,
        "extraction_status": status,
        "notes": notes,
    }


def process_casino(name, snippet, source_url, client, model):
    if snippet is None:
        return build_record(name, source_url, notes="Casino name or promotional terms not found in source text.")
    try:
        fields, notes = parse_model_output(call_model(client, model, name, snippet), snippet)
    except ModelOutputError as exc:
        log.error("%s: %s", name, exc)
        return build_record(name, source_url, status="failed", notes=str(exc))
    except Exception as exc:  # SDK/network errors vary; never pretend the AI step worked
        log.error("%s: language-model request failed: %s", name, exc)
        return build_record(name, source_url, status="failed", notes=f"Language-model request failed: {exc}")
    return build_record(name, source_url, fields, status_for(fields), " ".join(notes))


def assemble_dataset(source_url, records, now=None):
    now = now or datetime.now(timezone.utc)
    return {"last_updated": now.isoformat(timespec="seconds"), "source_url": source_url,
            "notes": "", "casinos": records}


def validate_dataset(data):
    """Return a list of problems (empty list means valid)."""
    errors = []
    if not isinstance(data, dict):
        return ["Top level must be an object."]
    for key in ("last_updated", "source_url", "casinos"):
        if key not in data:
            errors.append(f"Missing top-level key '{key}'.")
    if not isinstance(data.get("casinos"), list):
        return errors + ["'casinos' must be a list."]
    seen = set()
    for i, rec in enumerate(data["casinos"]):
        if not isinstance(rec, dict):
            errors.append(f"Record {i} is not an object.")
            continue
        for key in ("casino_name", "welcome_bonus", "wagering_requirement", "minimum_deposit",
                    "source_url", "extraction_status", "notes"):
            if key not in rec:
                errors.append(f"Record {i} missing '{key}'.")
        name = str(rec.get("casino_name", "")).strip().lower()
        if not name:
            errors.append(f"Record {i} has an empty casino_name.")
        elif name in seen:
            errors.append(f"Duplicate casino '{rec['casino_name']}'.")
        seen.add(name)
        for key in FIELDS:
            if rec.get(key) is not None and not isinstance(rec[key], str):
                errors.append(f"Record {i} field '{key}' must be a string or null.")
        if not validate_url(rec.get("source_url")):
            errors.append(f"Record {i} has an invalid source_url.")
        if rec.get("extraction_status") not in STATUSES:
            errors.append(f"Record {i} has an invalid extraction_status.")
    return errors


def has_usable_data(data):
    return any(r.get("extraction_status") in ("complete", "partial") for r in data.get("casinos", []))


def write_json_safely(path, new_data):
    """Write only if the new data is valid AND usable. Returns True if written.

    A failed scrape (nothing usable) never replaces an existing file.
    """
    errors = validate_dataset(new_data)
    if errors:
        log.error("Refusing to write invalid dataset: %s", "; ".join(errors))
        return False
    if not has_usable_data(new_data):
        log.error("No usable records extracted; keeping existing %s untouched.", path)
        return False
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(new_data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)  # atomic: readers never see a half-written file
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return True


# ---------- 5. Orchestration ----------

def parse_names(raw):
    names, seen = [], set()
    for n in (raw or "").split(","):
        n = n.strip()
        if n and n.lower() not in seen:
            names.append(n)
            seen.add(n.lower())
    return names


def run(source_url, names, output, model, user_agent, client=None, session=requests):
    """Return an exit code: 0 all complete, 2 written but incomplete, 1 failure."""
    if not validate_url(source_url):
        raise ScraperError("SOURCE_URL is missing or invalid. Set it in .env or pass --source-url.")
    if len(names) != 3:
        raise ScraperError(f"Exactly 3 casino names are required (got {len(names)}). Use --casinos 'A,B,C'.")
    client = client or make_client()
    check_robots(source_url, user_agent, session)
    text = extract_text(fetch_page(source_url, user_agent, session))
    log.info("Fetched %d characters of text from %s", len(text), source_url)
    snippets = find_snippets(text, names)
    records = [process_casino(n, snippets[n], source_url, client, model) for n in names]
    for r in records:
        log.info("%-25s %s", r["casino_name"], r["extraction_status"])
    if not write_json_safely(output, assemble_dataset(source_url, records)):
        return 1
    log.info("Wrote %s", output)
    return 0 if all(r["extraction_status"] == "complete" for r in records) else 2


def main(argv=None):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    ap = argparse.ArgumentParser(description="BonusAtlas casino bonus scraper")
    ap.add_argument("--source-url", default=os.environ.get("SOURCE_URL", ""))
    ap.add_argument("--casinos", default=os.environ.get("CASINO_NAMES", ""), help="Exactly three names, comma separated")
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    ap.add_argument("--user-agent", default=os.environ.get("USER_AGENT", DEFAULT_USER_AGENT))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return run(args.source_url, parse_names(args.casinos), args.output, args.model, args.user_agent)
    except ScraperError as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
