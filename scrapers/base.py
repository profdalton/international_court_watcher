"""Shared helpers for the per-court scrapers.

Each court scraper (icj.py, icc.py, echr.py, iacthr.py, itlos.py, wto.py)
exposes a single function `scrape() -> list[dict]` returning hearing
records in this shape:

    {
        "court": "echr",                 # matches a key in data/courts.json
        "case_name": "...",
        "date": "2026-09-22",            # ISO, first day if a range
        "time": "09:15",                 # "" if not published
        "hearing_type": "Chamber hearing",
        "location": "Strasbourg",
        "status": "scheduled",
        "url": "https://...",            # deep link if available, else the calendar page
    }

run_all.py calls each scraper, replaces that court's slice of
data/hearings.json with the fresh results, and leaves every other
court's entries untouched. If a scraper raises or returns nothing,
run_all.py keeps the previous data for that court rather than wiping
it — a broken selector should never blank out a page.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HEARINGS_PATH = ROOT / "data" / "hearings.json"

HEADERS = {
    # A realistic desktop UA. Several of these sites block the default
    # `python-requests` UA outright.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MONTHS = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
# Matches "22 September 2026" or "September 22, 2026"
DATE_RE = re.compile(
    rf"(?:(\d{{1,2}})\s+({MONTHS})\s+(\d{{4}})|({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}}))"
)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b")


def fetch(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_date(match: re.Match) -> date | None:
    g = match.groups()
    try:
        if g[0]:
            return datetime.strptime(f"{g[0]} {g[1]} {g[2]}", "%d %B %Y").date()
        return datetime.strptime(f"{g[3]} {g[4]} {g[5]}", "%B %d %Y").date()
    except ValueError:
        return None


def find_dates(text: str):
    """Yield (date, match_start, match_end) for every date-like substring."""
    for m in DATE_RE.finditer(text):
        d = parse_date(m)
        if d:
            yield d, m.start(), m.end()


def find_time(segment: str) -> str:
    m = TIME_RE.search(segment)
    if not m:
        return ""
    return f"{m.group(1).zfill(2)}:{m.group(2)}"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \u2014-:\u00a0")


def load_hearings() -> dict:
    if HEARINGS_PATH.exists():
        return json.loads(HEARINGS_PATH.read_text())
    return {"generated_at": "", "hearings": []}


def save_hearings(data: dict) -> None:
    data["generated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    HEARINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def replace_court(all_hearings: list[dict], court: str, fresh: list[dict]) -> list[dict]:
    """Swap in `fresh` records for `court`, leaving every other court's
    records untouched. If `fresh` is empty, keep whatever was there
    before — an empty result usually means the scraper broke, not that
    every hearing vanished."""
    if not fresh:
        return all_hearings
    kept = [h for h in all_hearings if h["court"] != court]
    return kept + fresh
