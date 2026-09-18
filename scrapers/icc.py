"""Scraper for the International Criminal Court's court calendar.

https://www.icc-cpi.int/court-calendar

Rewritten against the REAL rendered markup (inspected directly, not
guessed): the calendar is FullCalendar.js (the `fc-*` class names are
the library's own). Each week is one `.fc-content-skeleton` block
containing a <table> with two rows in lockstep, 7 columns each
(Mon–Sun):

  - <thead><tr>: 7 <td class="fc-day-top" data-date="YYYY-MM-DD">,
    one per day — the exact ISO date is right there in the attribute,
    no month-rollover guessing needed (unlike ksc.py's grid, which
    doesn't give you this and has to infer it from position).
  - <tbody><tr>: 7 <td>, empty except where a hearing exists, which
    then contains <a class="fc-day-grid-event"> with a
    <span class="fc-time"> and a <span class="fc-title"> (the case
    name, e.g. "El Hishri (Libya)").

The two rows share column position, so date_cells[i] and
body_cells[i] describe the same day — that's how each event gets its
date, via zip(), not inference.

Bonus found in the same markup: the page header lists "Courtroom I
/ II / III" as <li class="one">/"two"/"three">, and each event's
title span carries a matching class (e.g. "court-event-colour-one
one") — so which courtroom a hearing is in is recoverable too (see
_courtroom_for below) and gets folded into `location`.

Still uses base.fetch_rendered() (see that function's docstring) —
the calendar itself needs a real browser; a raw HTTP fetch here gets
only static shell (breadcrumb + the "Courtroom I/II/III" list) with
the actual grid populated by JS after load.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from base import clean, dump_debug, fetch_rendered

URL = "https://www.icc-cpi.int/court-calendar"

_COURTROOM_TOKENS = ("one", "two", "three")


def _courtroom_map(soup: BeautifulSoup) -> dict[str, str]:
    """{'one': 'Courtroom I', 'two': 'Courtroom II', ...} from the
    page's own <ul class="courtrooms"> legend."""
    mapping: dict[str, str] = {}
    for li in soup.select("ul.courtrooms li"):
        classes = li.get("class") or []
        text = clean(li.get_text())
        for token in _COURTROOM_TOKENS:
            if token in classes and text:
                mapping[token] = text
    return mapping


def _courtroom_for(event_tag, mapping: dict[str, str]) -> str | None:
    for el in event_tag.find_all(True):
        classes = el.get("class") or []
        for token in _COURTROOM_TOKENS:
            if token in classes and token in mapping:
                return mapping[token]
    return None


def scrape() -> list[dict]:
    try:
        html = fetch_rendered(URL, referer="https://www.icc-cpi.int/")
    except Exception as exc:  # noqa: BLE001
        print(f"[icc] rendered fetch failed: {exc}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    courtrooms = _courtroom_map(soup)

    entries = []
    for skeleton in soup.select(".fc-content-skeleton"):
        table = skeleton.find("table")
        if table is None:
            continue
        thead = table.find("thead")
        tbody = table.find("tbody")
        if thead is None or tbody is None:
            continue

        date_cells = thead.find_all("td", class_="fc-day-top")
        body_row = tbody.find("tr")
        if body_row is None:
            continue
        body_cells = body_row.find_all("td", recursive=False)

        for date_td, body_td in zip(date_cells, body_cells):
            date_str = date_td.get("data-date")
            if not date_str:
                continue

            for link in body_td.find_all("a", class_="fc-day-grid-event"):
                title_span = link.find("span", class_="fc-title")
                if title_span is None:
                    continue
                case_name = clean(title_span.get_text(" "))
                if not case_name:
                    continue

                time_span = link.find("span", class_="fc-time")
                time_text = clean(time_span.get_text()) if time_span else ""
                courtroom = _courtroom_for(link, courtrooms)

                entries.append(
                    {
                        "court": "icc",
                        "case_name": case_name,
                        "date": date_str,
                        "time": time_text,
                        "hearing_type": "Hearing",
                        "location": f"The Hague \u2014 {courtroom}" if courtroom else "The Hague",
                        "status": "scheduled",
                        "url": URL,
                    }
                )

    if not entries:
        debug_path = dump_debug("icc", html)
        print(f"[icc] no entries found in the FullCalendar grid — either genuinely "
              f"empty right now, or the markup shifted since this was last checked "
              f"against a real page. Raw HTML saved to {debug_path}.")
    else:
        print(f"[icc] parsed {len(entries)} entries")
    return entries


if __name__ == "__main__":
    import json

    print(json.dumps(scrape(), indent=2))
