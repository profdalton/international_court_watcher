"""Scraper for WTO Dispute Settlement Body meeting dates.

https://www.wto.org/english/news_e/events_e/events_list_view_e.htm

This is the WTO's general meetings calendar (all councils and
committees), which the live page lets you filter down to just the DSB
with JavaScript. The scraper instead fetches the server-rendered list
and keeps only rows whose text mentions "Dispute Settlement Body" —
this is the least well-verified scraper of the six since the page
leans on a client-side filter widget; treat results with extra
scepticism and check data/manual/wto.json as a override path if rows
stop coming through.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, fetch, find_dates

URL = "https://www.wto.org/english/news_e/events_e/events_list_view_e.htm"


def scrape() -> list[dict]:
    try:
        html = fetch(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[wto] fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all(["tr", "li", "div"])

    entries = []
    seen_dates = set()
    for row in rows:
        text = clean(row.get_text(" "))
        if "dispute settlement body" not in text.lower():
            continue
        # Skip the filter checkbox panel, which just lists body names
        # with no date attached.
        dates = list(find_dates(text))
        if not dates:
            continue
        d = dates[0][0]
        key = d.isoformat()
        if key in seen_dates:
            continue
        seen_dates.add(key)
        entries.append(
            {
                "court": "wto",
                "case_name": "Dispute Settlement Body meeting",
                "date": d.isoformat(),
                "time": "",
                "hearing_type": "DSB meeting",
                "location": "Geneva",
                "status": "scheduled",
                "url": URL,
            }
        )

    if not entries:
        print("[wto] no DSB rows found — page may rely on JS filtering")
    else:
        print(f"[wto] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
