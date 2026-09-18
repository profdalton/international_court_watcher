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
"""
from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from base import clean, fetch

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
        html = fetch(_month_url(year, month))
    except Exception as exc:  # noqa: BLE001
        print(f"[ksc] fetch failed for {year}-{month:02d}: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        print(f"[ksc] no calendar table found for {year}-{month:02d}")
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
