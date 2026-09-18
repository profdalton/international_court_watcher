"""Scraper for the ITLOS "Calendar of Events" feed.

https://www.itlos.org/en/main/resources/calendar-of-events/

This is NOT a hearings calendar — it's a reverse-chronological press
feed mixing workshop announcements, judge elections, condolences,
case orders, and (occasionally) actual hearing news, with nothing in
the markup distinguishing one kind from another. Regexing "upcoming
hearing" out of free text here would be guesswork dressed up as data
(a filing-deadline date mentioned in a sentence looks identical to a
hearing date to a date-matching regex), so this deliberately does NOT
try to classify items as hearings.

Instead it just extracts the most recent items as plain announcements
— date, title, one-line summary, a link — and itlos.html shows them
in their own "Recent announcements" section, separate from the
(usually empty) structured hearings feed every other court page uses.
See run_all.py: this writes to data/itlos-news.json, not
data/hearings.json, so it never pollutes the cross-court feed or
counts.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from base import ROOT, clean, dump_debug, fetch, find_dates

URL = "https://www.itlos.org/en/main/resources/calendar-of-events/"
NEWS_PATH = ROOT / "data" / "itlos-news.json"
MAX_ITEMS = 8
PURE_DATE_RE = re.compile(r"^\d{1,2}\s+\w+\s+\d{4}$")


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[itlos_news] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    items = []
    current = None

    def flush():
        if current and current.get("title"):
            items.append(current)

    # The date is plain, short text sitting somewhere near each item —
    # its exact tag varies by CMS theme (p, span, div, time all seen
    # in the wild for this kind of "date above headline" layout), so
    # rather than guess one tag, this matches any *leaf* element (no
    # child tags of its own — ruling out wrapper divs/sections whose
    # get_text() would swallow the whole item) whose text is only a
    # date. Titles still come from real headings; links from <a>.
    candidates = main.find_all(["h2", "h3", "h4", "p", "span", "div", "time", "a"])
    for tag in candidates:
        text = clean(tag.get_text(" "))
        if not text:
            continue

        is_leaf = tag.find(True) is None
        if tag.name != "a" and is_leaf and PURE_DATE_RE.match(text):
            dates = list(find_dates(text))
            if not dates:
                continue
            flush()
            current = {"date": dates[0][0].isoformat(), "url": URL}
            continue

        if current is None:
            continue

        if tag.name in ("h2", "h3", "h4") and "title" not in current:
            current["title"] = text
            continue

        if tag.name == "p" and is_leaf and "title" in current and "summary" not in current:
            current["summary"] = text[:200]
            continue

        if tag.name == "a" and current.get("url") == URL:
            href = tag.get("href")
            if href and href.startswith("http"):
                current["url"] = href

    flush()
    items = items[:MAX_ITEMS]
    if not items:
        debug_path = dump_debug("itlos_news", html)
        print(f"[itlos_news] parsed 0 announcements — worked against synthetic test "
              f"markup but not the live page, so the real markup differs from what "
              f"was assumed (likely which tag wraps each item's date). Raw HTML "
              f"saved to {debug_path} — look for the date text near the first news "
              f"item and check what tag actually contains it.")
    else:
        print(f"[itlos_news] parsed {len(items)} announcements")
    return items


def save(items: list[dict]) -> None:
    import json
    from datetime import datetime

    NEWS_PATH.write_text(
        json.dumps(
            {"generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "items": items},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
