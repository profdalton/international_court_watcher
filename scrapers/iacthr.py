"""Scraper for the Inter-American Court of Human Rights' session dates.

https://www.corteidh.or.cr/periodo_de_sesiones.cfm?lang=en

Unlike the other courts, this page publishes session *periods*
("192nd Regular Session from June 29 to July 3") rather than individual
hearings with a time. Each session becomes one entry, dated to its
start day, with the date range folded into hearing_type. Entries for
the current year are usually listed without an explicit year on the
page, so when a match has none this assumes the current UTC year.

The page is a running archive — it lists years of past sessions below
the current ones, not just what's upcoming — so this drops anything
that already ended more than a few days ago. That also limits (but
doesn't fully eliminate) the damage if a genuinely old, year-less
entry ever gets mis-dated into the current year by the fallback
above: it would need to also land within the recent-past/future
window to slip through.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from base import clean, dump_debug, fetch

URL = "https://www.corteidh.or.cr/periodo_de_sesiones.cfm?lang=en"
STALE_CUTOFF_DAYS = 3  # drop sessions that ended more than this long ago

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

    text = clean(BeautifulSoup(html, "html.parser").get_text(" "))

    this_year = datetime.utcnow().year
    cutoff = date.today() - timedelta(days=STALE_CUTOFF_DAYS)
    entries = []
    skipped_stale = 0
    for m in SESSION_RE.finditer(text):
        num, start_month, start_day, end_month, end_day, year = m.groups()
        year = int(year) if year else this_year
        end_month = end_month or start_month
        try:
            start = datetime.strptime(f"{start_month} {start_day} {year}", "%B %d %Y").date()
            end = datetime.strptime(f"{end_month} {end_day} {year}", "%B %d %Y").date()
        except ValueError:
            continue

        if end < cutoff:
            skipped_stale += 1
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

    if not entries:
        debug_path = dump_debug("iacthr", html)
        print(f"[iacthr] parsed 0 entries ({skipped_stale} matched but were stale) — "
              f"this scraper has no 'confirmed empty' marker (this court has sessions "
              f"most of the year, so 0 is unlikely to be genuinely correct), meaning "
              f"the SESSION_RE pattern probably doesn't match the live page's actual "
              f"wording. Raw HTML saved to {debug_path} — compare it against "
              f"SESSION_RE in this file.")
    else:
        print(f"[iacthr] parsed {len(entries)} entries ({skipped_stale} older sessions skipped)")
    return entries


def _ordinal_suffix(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
