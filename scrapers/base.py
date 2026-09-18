"""Shared helpers for the per-court scrapers.

Each court scraper (icj.py, icc.py, echr.py, iacthr.py, itlos.py,
ksc.py, wto.py) exposes a single function `scrape() -> list[dict]`
returning hearing records in this shape:

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
import time
from datetime import date, datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent.parent
HEARINGS_PATH = ROOT / "data" / "hearings.json"

HEADERS = {
    # A full, realistic Chrome-on-Windows header set. Several of these
    # sites block bare `python-requests` (default UA, no Accept, no
    # Sec-Fetch-* headers) even when they don't run a full JS
    # challenge — this is the "look like a normal tab opening the
    # page" version, not a strong workaround for something like
    # Cloudflare's managed challenge.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    # Deliberately NOT setting Accept-Encoding here. `requests` sets a
    # safe default on its own (gzip, deflate — both handled by the
    # stdlib, no extra dependency) based on what it can actually
    # decompress. Claiming "br" (Brotli) without the optional `brotli`
    # package installed caused a real bug: the server would send
    # Brotli-compressed bodies that never got decoded, and resp.text
    # returned raw compressed bytes decoded as garbage text — which
    # silently broke ICJ, ITLOS, and IACtHR at once (all three do
    # support Brotli; ECHR apparently doesn't, which is why it kept
    # working). If Brotli support is ever added on purpose, add
    # `brotli` to requirements.txt *first*.
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
}

_session = requests.Session()
_session.headers.update(HEADERS)
_retry = Retry(
    total=3,
    backoff_factor=1.5,  # 1.5s, 3s, 6s between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))

MONTHS = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
# Matches "22 September 2026" or "September 22, 2026"
DATE_RE = re.compile(
    rf"(?:(\d{{1,2}})\s+({MONTHS})\s+(\d{{4}})|({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}}))"
)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b")


def fetch(url: str, timeout: int = 30, referer: str | None = None) -> str:
    """GET a page with browser-like headers, retrying transient errors
    (timeouts, 5xx, 429) up to 3 times with backoff. A 403/401 is
    treated as a real block, not a transient error, and is raised
    immediately — retrying with the same headers won't help; that
    means the site's bot protection is doing more than a UA check
    (see the module docstrings in icc.py / ksc.py for what to try
    next in that case).
    """
    req_headers = {"Referer": referer} if referer else {}
    resp = _session.get(url, headers=req_headers, timeout=timeout)
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


DEBUG_DIR = ROOT / "scrapers" / ".debug"


def dump_debug(label: str, html: str) -> str:
    """Save the raw HTML a scraper fetched to scrapers/.debug/<label>.html.

    Call this when a scraper's result is ambiguous — fetch succeeded
    but nothing was parsed and no "confirmed empty" marker matched.
    Printing a text snippet is rarely enough to tell a genuinely empty
    docket apart from a changed marker, a cookie-consent wall, or a
    WAF interstitial that returned 200 instead of blocking outright;
    the full saved file lets you (or a future debugging session)
    actually look. Not committed — see .gitignore.
    """
    DEBUG_DIR.mkdir(exist_ok=True)
    path = DEBUG_DIR / f"{label}.html"
    path.write_text(html, errors="replace")
    return str(path.relative_to(ROOT))


def replace_court(all_hearings: list[dict], court: str, fresh: list[dict]) -> list[dict]:
    """Swap in `fresh` records for `court`, leaving every other court's
    records untouched. If `fresh` is empty, keep whatever was there
    before — an empty result usually means the scraper broke, not that
    every hearing vanished."""
    if not fresh:
        return all_hearings
    kept = [h for h in all_hearings if h["court"] != court]
    return kept + fresh
