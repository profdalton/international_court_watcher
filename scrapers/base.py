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

from curl_cffi.requests import Session
from curl_cffi.requests.exceptions import HTTPError, RequestException

ROOT = Path(__file__).resolve().parent.parent
HEARINGS_PATH = ROOT / "data" / "hearings.json"

# Which real browser's TLS/HTTP fingerprint curl_cffi impersonates.
# This is the actual fix for ICC/KSC's 403s (as far as we could tell
# without live access to test against): plain `requests` (via
# urllib3/OpenSSL) has a TLS handshake that's trivially distinguishable
# from a real browser's, no matter how convincing the headers look.
# curl_cffi wraps libcurl with a patched TLS stack that reproduces a
# specific real browser's handshake, which is what a WAF checking for
# that fingerprint actually cares about. If ICC/KSC still 403 with
# this, the fingerprint isn't the (only) thing being checked — see the
# "Known rough edges" section of the README for the next step
# (a real headless browser).
IMPERSONATE = "chrome124"

HEADERS = {
    # curl_cffi's `impersonate` already sets a matching User-Agent and
    # the low-level TLS/HTTP2 fingerprint; these are the extra bits
    # worth setting on top of that.
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_session = Session(impersonate=IMPERSONATE, headers=HEADERS)

MONTHS = (
    "January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
# Matches "22 September 2026" or "September 22, 2026"
DATE_RE = re.compile(
    rf"(?:(\d{{1,2}})\s+({MONTHS})\s+(\d{{4}})|({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}}))"
)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 1.5  # 1.5s, 3s between attempts


def fetch(url: str, timeout: int = 30, referer: str | None = None) -> str:
    """GET a page impersonating a real Chrome TLS/HTTP fingerprint
    (see IMPERSONATE above), retrying transient errors (timeouts,
    connection errors, 5xx, 429) up to 3 times with backoff. A 403/401
    is treated as a real block, not a transient error, and is raised
    immediately — retrying the identical request won't help; if this
    still happens with curl_cffi, the WAF is checking something beyond
    the TLS fingerprint (see icc.py / ksc.py docstrings).
    """
    req_headers = {"Referer": referer} if referer else {}
    last_exc: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = _session.get(url, headers=req_headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                last_exc = exc
                time.sleep(_BACKOFF_SECONDS * attempt)
                continue
            raise
        except RequestException as exc:
            # Connection errors, timeouts, and other libcurl-level
            # failures — worth a retry, unlike a definitive HTTP status.
            if attempt < _MAX_ATTEMPTS:
                last_exc = exc
                time.sleep(_BACKOFF_SECONDS * attempt)
                continue
            raise

    raise last_exc  # pragma: no cover — loop always returns or raises above


# A handful of very different browser fingerprints to try in sequence
# when the default IMPERSONATE gets a flat 403 — worth a shot before
# concluding a site needs a real headless browser, since some WAFs
# key on specific fingerprints (an outdated-looking one, or one seen
# in a lot of scraper traffic) rather than "is this curl_cffi at
# all". No retries within each attempt (a 403 isn't transient), so
# this is fast even when every fingerprint fails.
FALLBACK_FINGERPRINTS = ("chrome136", "safari184", "firefox147", "edge101")


def fetch_try_fingerprints(
    url: str, timeout: int = 30, referer: str | None = None
) -> tuple[str, str]:
    """Like fetch(), but on a 403 tries each of FALLBACK_FINGERPRINTS
    before giving up, returning (html, fingerprint_that_worked). Use
    this for a site still 403ing under the default IMPERSONATE — it's
    slower (up to len(FALLBACK_FINGERPRINTS) sequential attempts) so
    it's not the default for every scraper.
    """
    req_headers = {"Referer": referer} if referer else {}
    last_exc: Exception | None = None

    for fp in (IMPERSONATE, *FALLBACK_FINGERPRINTS):
        try:
            resp = _session.get(url, headers=req_headers, timeout=timeout, impersonate=fp)
            resp.raise_for_status()
            return resp.text, fp
        except HTTPError as exc:
            last_exc = exc
            continue
        except RequestException as exc:
            last_exc = exc
            continue

    raise last_exc


# ---------------------------------------------------------------
# Real-browser fetch, for pages that render via JavaScript (ICC) or
# whose WAF isn't satisfied by any curl_cffi fingerprint (KSC).
# Playwright drives an actual headless Chromium, so it executes JS
# and presents a real TLS/HTTP stack a WAF can't distinguish from a
# person's browser. It's much heavier than fetch()/fetch_try_
# fingerprints() — a browser process per call, seconds instead of
# milliseconds — so use it only where those genuinely aren't enough.
#
# Needs `playwright install chromium` run once (locally, and as a
# step in the GitHub Actions workflow) to download the browser
# binary — installing the `playwright` pip package alone is not
# enough. See README.md.
# ---------------------------------------------------------------
_pw = None
_browser = None


def _get_browser():
    """Lazily start one Playwright instance + browser process, shared
    across every fetch_rendered() call in this run, and registered to
    close automatically when the script exits."""
    global _pw, _browser
    if _browser is None:
        import atexit

        from playwright.sync_api import sync_playwright

        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=True)
        atexit.register(_close_browser)
    return _browser


def _close_browser():
    global _pw, _browser
    if _browser is not None:
        _browser.close()
        _browser = None
    if _pw is not None:
        _pw.stop()
        _pw = None


def fetch_rendered(
    url: str,
    timeout: int = 30,
    referer: str | None = None,
    wait_selector: str | None = None,
    extra_wait_ms: int = 3000,
) -> str:
    """Load a page in headless Chromium and return the DOM after JS
    has run, instead of the raw server response fetch()/fetch_try_
    fingerprints() return.

    Uses wait_until="domcontentloaded" rather than "networkidle" —
    the latter waits for a stretch of complete network silence, which
    plenty of ordinary sites never reach (analytics beacons, ad
    trackers, chat widgets, polling) and can hang for the full
    timeout even on a page that rendered fine. domcontentloaded fires
    once the initial HTML/DOM is ready, and the extra_wait_ms /
    wait_selector below give the page's own JS time to actually
    populate content after that.

    wait_selector: a CSS selector to wait for before reading the page
    (e.g. a row that only appears once the calendar has actually
    populated). If given but never appears, this falls through and
    returns whatever loaded anyway rather than raising — a partial
    page is more useful for debugging than nothing. If omitted, this
    just waits `extra_wait_ms` after the DOM is ready, which is
    cruder but doesn't require knowing the real selector in advance.
    """
    browser = _get_browser()
    extra_headers = {"Referer": referer} if referer else {}
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        extra_http_headers=extra_headers,
    )
    try:
        page = context.new_page()
        page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=timeout * 1000)
            except Exception:  # noqa: BLE001
                pass  # return whatever DID load rather than raising
        else:
            page.wait_for_timeout(extra_wait_ms)
        return page.content()
    finally:
        context.close()


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
