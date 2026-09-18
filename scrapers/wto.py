"""Scraper for WTO Dispute Settlement Body meeting dates.

https://www.wto.org/english/news_e/events_e/events_list_view_e.htm

This is the WTO's general meetings calendar (all councils and
committees), which the live page lets you filter down to just the DSB
with JavaScript. A plain HTTP fetch found 0 DSB rows — consistent
with (though not as directly confirmed as ICC's case) the calendar
being populated client-side, so this uses base.fetch_rendered() too.
Still the least-verified of the seven scrapers: even with real
rendered content, the row-scanning logic below (keep any row whose
text mentions "Dispute Settlement Body" with a date in it) is a
guess about the real structure, not something tested against it. If
it still finds nothing after switching to a real browser, the debug
dump (still triggered on 0 results) is the next thing to check, and
data/manual/wto.json is the override path either way.

Needs `playwright install chromium` (see README) — installing the
`playwright` pip package alone does not download the browser.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, dump_debug, fetch_rendered, find_dates

URL = "https://www.wto.org/english/news_e/events_e/events_list_view_e.htm"


def scrape() -> list[dict]:
    try:
        html = fetch_rendered(URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[wto] rendered fetch failed: {exc}")
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
        debug_path = dump_debug("wto", html)
        print(f"[wto] no DSB rows found even in the JS-rendered page. Raw HTML "
              f"saved to {debug_path}; search it for 'Dispute Settlement Body' to "
              f"see whether real meeting rows made it in, and if so, what they "
              f"actually look like (the row-scanning logic in this file may need "
              f"rewriting to match).")
    else:
        print(f"[wto] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
