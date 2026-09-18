"""Scraper for the Kosovo Specialist Chambers calendar.

https://www.scp-ks.org/en/calendar

Unlike the other courts, this is a month-grid calendar (a literal
table of days), paged with ?calendar_timestamp=YYYY-MM, rather than a
flat list of upcoming entries. Only some day cells carry a link to an
event ("KSC Press Briefing - 14:30", "Summer Court Recess 2026", a
hearing name, etc.) — most days have none.

This fetches the current month plus the next two, walks the calendar
table in row-major order, and works out which cells belong to the
target month vs. the leading/trailing days of the adjacent months
that a grid always shows a few of (heuristic: the first row's high
day-numbers belong to the previous month, the last row's low
day-numbers belong to the next month). That heuristic is the part
most likely to need a fix once this runs against the live page.

Confirmed 403 Forbidden under plain `requests` (full browser headers)
AND under curl_cffi's every available TLS fingerprint AND under a
real headless Chromium via Playwright — that last one showed the
actual reason: a Cloudflare-style "performing security verification"
interstitial. This isn't a fingerprint or JS-rendering problem
anymore; it's active bot detection flagging the automated browser
itself. `_scrape_month` now waits longer (7s vs. the 3s default) on
the theory that a non-interactive challenge might clear on its own,
and explicitly detects the challenge page so failures are reported
accurately instead of looking like "no table found". If the longer
wait doesn't clear it either, this is a genuinely hard wall —
further options exist (stealth-patched browser automation,
CAPTCHA-solving services) but they're an escalating arms race against
a security product built to resist exactly that, which isn't a
proportionate amount of engineering for one tribunal's calendar.
data/manual/ksc.json is the sensible stopping point at that stage,
not a consolation prize.

Needs `playwright install chromium` (see README) — installing the
`playwright` pip package alone does not download the browser.
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from base import clean, dump_debug, fetch_rendered

BASE_URL = "https://www.scp-ks.org/en/calendar"
TIME_IN_TITLE_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _absolute(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return href
    return f"https://www.scp-ks.org{href}"


def _month_url(year: int, month: int) -> str:
    return f"{BASE_URL}?calendar_timestamp={year:04d}-{month:02d}"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _hearing_type(title: str) -> str:
    t = title.lower()
    if "recess" in t:
        return "Court recess"
    if "briefing" in t:
        return "Press briefing"
    if "status conference" in t:
        return "Status conference"
    if "hearing" in t or "trial" in t or "session" in t:
        return "Court session"
    return "Calendar event"


def _scrape_month(year: int, month: int) -> list[dict]:
    try:
        # Longer wait than the default: KSC showed a Cloudflare-style
        # "performing security verification" interstitial on the last
        # run, which (if it's a non-interactive/managed challenge, not
        # one requiring a click) sometimes clears on its own given a
        # few extra seconds for the browser-check JS to finish and the
        # page to redirect to the real content.
        html = fetch_rendered(_month_url(year, month), referer=BASE_URL, extra_wait_ms=7000)
    except Exception as exc:  # noqa: BLE001
        print(f"[ksc] rendered fetch failed for {year}-{month:02d}: {exc}")
        return []

    if "security verification" in html.lower() or "checking your browser" in html.lower():
        debug_path = dump_debug(f"ksc-{year}-{month:02d}", html)
        print(f"[ksc] {year}-{month:02d} still stuck on a bot-challenge page even "
              f"after waiting and even with a real headless browser. Raw HTML saved "
              f"to {debug_path}. This is a harder block than a TLS fingerprint or a "
              f"missing-JS problem — likely Cloudflare (or similar) detecting the "
              f"browser as automated specifically, not just \"not a browser\". "
              f"data/manual/ksc.json is the realistic path forward rather than "
              f"chasing more evasion techniques.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        debug_path = dump_debug(f"ksc-{year}-{month:02d}", html)
        print(f"[ksc] no calendar table found for {year}-{month:02d} even after "
              f"JS rendering and clearing the challenge page. Raw HTML saved to "
              f"{debug_path} — check whether the table uses a different "
              f"tag/structure than expected.")
        return []

    cells = table.find_all("td")
    n = len(cells)
    cols = 7
    last_row_start = (n - 1) // cols * cols

    entries = []
    for i, cell in enumerate(cells):
        day_text = clean(cell.get_text(" ")).split(" ")[0] if cell.get_text(strip=True) else ""
        links = cell.find_all("a")
        if not links or not day_text.isdigit():
            continue
        day_num = int(day_text)

        row = i // cols
        if row == 0 and day_num > 7:
            y, m = _prev_month(year, month)
        elif row >= last_row_start // cols and day_num <= 7 and i > n // 2:
            y, m = _next_month(year, month)
        else:
            y, m = year, month

        try:
            d = date(y, m, day_num)
        except ValueError:
            continue

        for link in links:
            title = clean(link.get_text(" "))
            if not title:
                continue
            time_match = TIME_IN_TITLE_RE.search(title)
            entries.append(
                {
                    "court": "ksc",
                    "case_name": title,
                    "date": d.isoformat(),
                    "time": f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "",
                    "hearing_type": _hearing_type(title),
                    "location": "The Hague",
                    "status": "scheduled",
                    "url": _absolute(link.get("href")) or BASE_URL,
                }
            )

    return entries


def scrape() -> list[dict]:
    today = date.today()
    year, month = today.year, today.month

    entries: list[dict] = []
    for _ in range(3):  # current month + next two
        entries.extend(_scrape_month(year, month))
        year, month = _next_month(year, month)

    print(f"[ksc] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
