"""Scraper for the Inter-American Court of Human Rights' session dates.

https://www.corteidh.or.cr/periodo_de_sesiones.cfm?lang=en

Unlike the other courts, this page publishes session *periods*
("192nd Regular Session from June 29 to July 3") rather than individual
hearings with a time. Each session becomes one entry, dated to its
start day, with the date range folded into hearing_type. Entries for
the current year are usually listed without an explicit year on the
page, so when a match has none this assumes the current UTC year.
"""
from __future__ import annotations

import re
from datetime import datetime

from base import clean, fetch

URL = "https://www.corteidh.or.cr/periodo_de_sesiones.cfm?lang=en"

SESSION_RE = re.compile(
    r"(\d+)(?:st|nd|rd|th)\s+Regular Session\s+[Ff]rom\s+"
    r"([A-Za-z]+)\s+(\d{1,2})\s+to\s+"
    r"(?:([A-Za-z]+)\s+)?(\d{1,2})(?:,?\s*(\d{4}))?"
)


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[iacthr] fetch failed: {exc}")
        return []

    text = clean(html.replace("<", " <"))
    # Fall back to a lighter strip if the page is mostly plain text
    from bs4 import BeautifulSoup

    text = clean(BeautifulSoup(html, "html.parser").get_text(" "))

    this_year = datetime.utcnow().year
    entries = []
    for m in SESSION_RE.finditer(text):
        num, start_month, start_day, end_month, end_day, year = m.groups()
        year = int(year) if year else this_year
        end_month = end_month or start_month
        try:
            start = datetime.strptime(f"{start_month} {start_day} {year}", "%B %d %Y").date()
            end = datetime.strptime(f"{end_month} {end_day} {year}", "%B %d %Y").date()
        except ValueError:
            continue

        entries.append(
            {
                "court": "iacthr",
                "case_name": f"{num}{_ordinal_suffix(int(num))} Regular Session",
                "date": start.isoformat(),
                "time": "",
                "hearing_type": f"Regular session, through {end.strftime('%d %b %Y')}",
                "location": "San Jos\u00e9, Costa Rica",
                "status": "scheduled",
                "url": URL,
            }
        )

    print(f"[iacthr] parsed {len(entries)} entries")
    return entries


def _ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
