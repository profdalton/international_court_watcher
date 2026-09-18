"""Scraper for the International Court of Justice calendar of hearings.

https://www.icj-cij.org/calendar

When nothing is scheduled the page just says so in a heading ("No
public hearing of the Court is currently scheduled."); this returns an
empty list in that case rather than treating it as a failure. When
hearings are listed, this walks headings/paragraphs in document order
looking for date + case-name pairs, the same general strategy as the
ECHR scraper, since the exact Drupal view markup isn't something we
can pin down without a live example to test against.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, fetch, find_dates, find_time

URL = "https://www.icj-cij.org/calendar"
NO_HEARING_MARKERS = ("no public hearing", "no hearing")


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[icj] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    full_text = clean(main.get_text(" ")).lower()

    if any(marker in full_text for marker in NO_HEARING_MARKERS):
        print("[icj] no hearings currently scheduled")
        return []

    entries = []
    current = None

    def flush():
        if current and current.get("case_name"):
            entries.append(
                {
                    "court": "icj",
                    "case_name": current["case_name"],
                    "date": current["date"].isoformat(),
                    "time": current.get("time", ""),
                    "hearing_type": current.get("hearing_type", "Public sitting"),
                    "location": "The Hague",
                    "status": "scheduled",
                    "url": URL,
                }
            )

    for tag in main.find_all(["h2", "h3", "h4", "p", "li"]):
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
    print(f"[icj] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
