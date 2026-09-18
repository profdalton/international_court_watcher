"""Scraper for the European Court of Human Rights calendar of hearings.

https://www.echr.coe.int/calendar-of-hearings

The page lists entries as a repeating block: a date heading, a case-name
heading, a hearing-type line ("Chamber hearing" / "Grand Chamber
hearing"), a "<date> at <time>" line, then a few reference links. This
walks the headings/paragraphs in document order and groups them by
date heading rather than relying on specific CSS classes, since the
Council of Europe site's markup has changed shape before.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from base import clean, fetch, find_dates, find_time

URL = "https://www.echr.coe.int/calendar-of-hearings"
PURE_DATE_RE = re.compile(r"^\d{1,2}\s+\w+\s+\d{4}$")


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[echr] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    blocks = []
    for tag in main.find_all(["h2", "h3", "h4", "p"]):
        text = clean(tag.get_text(" "))
        if text:
            blocks.append(text)

    entries = []
    current = None

    def flush():
        if current and current.get("case_name"):
            entries.append(
                {
                    "court": "echr",
                    "case_name": current["case_name"],
                    "date": current["date"].isoformat(),
                    "time": current.get("time", ""),
                    "hearing_type": current.get("hearing_type", "Hearing"),
                    "location": "Strasbourg",
                    "status": "scheduled",
                    "url": URL,
                }
            )

    for text in blocks:
        if PURE_DATE_RE.match(text):
            dates = list(find_dates(text))
            if not dates:
                continue
            flush()
            current = {"date": dates[0][0]}
            continue

        if current is None:
            continue

        if "case_name" not in current:
            # skip the (usually empty) image placeholder text
            if text and not text.lower().startswith("responsive image"):
                current["case_name"] = text
            continue

        if "hearing" in text.lower() and len(text) < 60:
            current["hearing_type"] = text
            continue

        t = find_time(text)
        if t:
            current["time"] = t

    flush()
    print(f"[echr] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
