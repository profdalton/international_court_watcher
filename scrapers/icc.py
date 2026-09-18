"""Scraper for the International Criminal Court's court calendar.

https://www.icc-cpi.int/court-calendar

Confirmed 403 Forbidden on a plain fetch, including with a full
browser-style header set (see base.HEADERS) — this is not just a bare
`python-requests` User-Agent being blocklisted, so it's likely a WAF
doing something more (IP reputation, a JS/cookie challenge, or TLS
fingerprinting that the `requests` library can't reproduce). Realistic
next steps if this keeps failing from GitHub Actions too:

1. Individual calendar entries appear to live at their own URLs
   (e.g. /court-calendar/icc-official-holiday) with structured
   CalendarID / CaseName / Courtroom / DateOfHearing fields — worth
   checking whether those are reachable even when the main calendar
   page isn't, or whether the main page calls a JSON endpoint (check
   a real browser's Network tab).
2. A headless-browser fetch (Playwright/Selenium) would clear a JS
   challenge that plain `requests` cannot; that's a bigger dependency
   than this project currently carries, so it isn't wired in by
   default.
3. Drop hand-maintained entries in data/manual/icc.json (same record
   shape as scrape() returns) and run_all.py will merge them in on
   top of whatever this scraper manages to find.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, fetch, find_dates, find_time

URL = "https://www.icc-cpi.int/court-calendar"


def scrape() -> list[dict]:
    try:
        html = fetch(URL, referer="https://www.icc-cpi.int/")
    except Exception as exc:  # noqa: BLE001
        print(f"[icc] fetch failed (likely bot protection): {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    entries = []
    current = None

    def flush():
        if current and current.get("case_name"):
            entries.append(
                {
                    "court": "icc",
                    "case_name": current["case_name"],
                    "date": current["date"].isoformat(),
                    "time": current.get("time", ""),
                    "hearing_type": current.get("hearing_type", "Hearing"),
                    "location": "The Hague",
                    "status": "scheduled",
                    "url": URL,
                }
            )

    for tag in main.find_all(["h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd"]):
        text = clean(tag.get_text(" "))
        if not text:
            continue

        dates = list(find_dates(text))
        if dates and len(text) < 40:
            flush()
            current = {"date": dates[0][0]}
            continue

        if current is None:
            continue

        if "case_name" not in current:
            current["case_name"] = text
            continue

        t = find_time(text)
        if t:
            current["time"] = t
        if len(text) < 60:
            current.setdefault("hearing_type", text)

    flush()
    if not entries:
        print("[icc] no structured entries found — page may need JS or is blocked")
    else:
        print(f"[icc] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
