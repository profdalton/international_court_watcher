#!/usr/bin/env python3
"""Run every court scraper and update data/hearings.json.

Usage: python scrapers/run_all.py
Runs daily via .github/workflows/update-calendar.yml.

A scraper that raises or returns [] leaves that court's existing
entries alone (see base.replace_court) — a bad run should never wipe
a court's page. Optional hand-maintained records in
data/manual/<slug>.json are merged in after scraping, keyed by
(date, case_name), so a manual entry can plug a gap without being
duplicated if the scraper later starts finding it too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from base import ROOT, load_hearings, replace_court, save_hearings

import echr
import iacthr
import icc
import icj
import itlos
import itlos_news
import ksc
import wto

SCRAPERS = {
    "icj": icj.scrape,
    "icc": icc.scrape,
    "echr": echr.scrape,
    "iacthr": iacthr.scrape,
    "itlos": itlos.scrape,
    "ksc": ksc.scrape,
    "wto": wto.scrape,
}

MANUAL_DIR = ROOT / "data" / "manual"


def load_manual(slug: str) -> list[dict]:
    path = MANUAL_DIR / f"{slug}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def merge_manual(fresh: list[dict], manual: list[dict]) -> list[dict]:
    if not manual:
        return fresh
    seen = {(h["date"], h["case_name"]) for h in fresh}
    return fresh + [m for m in manual if (m["date"], m["case_name"]) not in seen]


def main() -> None:
    data = load_hearings()
    all_hearings = data.get("hearings", [])

    for slug, scrape_fn in SCRAPERS.items():
        try:
            fresh = scrape_fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[{slug}] scraper crashed: {exc}")
            fresh = []
        fresh = merge_manual(fresh, load_manual(slug))
        all_hearings = replace_court(all_hearings, slug, fresh)

    data["hearings"] = sorted(all_hearings, key=lambda h: (h["date"], h.get("time", "")))
    save_hearings(data)
    print(f"wrote {len(all_hearings)} total hearings to data/hearings.json")

    try:
        news_items = itlos_news.scrape()
        if news_items:
            itlos_news.save(news_items)
            print(f"wrote {len(news_items)} items to data/itlos-news.json")
    except Exception as exc:  # noqa: BLE001
        print(f"[itlos_news] crashed, leaving data/itlos-news.json untouched: {exc}")


if __name__ == "__main__":
    main()
