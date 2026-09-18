"""Scraper for the International Tribunal for the Law of the Sea's
schedule of hearings.

https://www.itlos.org/en/main/cases/schedule-of-hearings/

Same shape as icj.py: an explicit "no dates set" message when the
docket is empty, otherwise a list of date + case entries walked in
document order.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, fetch, find_dates, find_time

URL = "https://www.itlos.org/en/main/cases/schedule-of-hearings/"
NO_HEARING_MARKERS = ("no dates set", "no hearing")


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[itlos] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    full_text = clean(main.get_text(" ")).lower()

    if any(marker in full_text for marker in NO_HEARING_MARKERS):
        print("[itlos] no hearings currently scheduled")
        return []

    entries = []
    current = None

    def flush():
        if current and current.get("case_name"):
            entries.append(
                {
                    "court": "itlos",
                    "case_name": current["case_name"],
                    "date": current["date"].isoformat(),
                    "time": current.get("time", ""),
                    "hearing_type": current.get("hearing_type", "Public hearing"),
                    "location": "Hamburg",
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
    print(f"[itlos] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
