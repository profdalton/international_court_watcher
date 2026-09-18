#!/usr/bin/env python3
"""Generate courts/<slug>.html for every court listed in data/courts.json.

This only needs to be rerun when a court is added, removed, or its
metadata changes — not on every scrape. The hearing data itself is
loaded client-side from data/hearings.json, so these pages stay valid
without regeneration as new hearings come in.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COURTS = json.loads((ROOT / "data" / "courts.json").read_text())

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{name} ({abbr}) hearings — International Court Watcher</title>
  <meta name="description" content="Upcoming hearings and sessions at the {name}, sourced from the court's own calendar.">
  <link rel="icon" href="../assets/img/favicon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../assets/css/style.css">
</head>
<body data-root="..">
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="../index.html">
        <img src="../assets/img/logo.png" alt="International Court Watcher logo">
        <span class="brand-name">International <span>Court</span> Watcher</span>
      </a>
      <nav class="site-nav">
        <a href="../index.html#courts">Courts</a>
        <a href="../about.html">About</a>
        <a class="github" href="https://github.com/" target="_blank" rel="noopener">Source</a>
      </nav>
    </div>
  </header>

  <section class="court-header" style="--page-accent:{accent}">
    <div class="wrap">
      <span class="abbr-tag">{abbr}</span>
      <h1>{name}</h1>
      <p class="blurb">{blurb}</p>
      <div class="court-meta">
        <div><span>Seat</span>{seat}</div>
        <div><span>Established</span>{established}</div>
        <div><span>System</span>{system}</div>
        <div><span>Official calendar</span><a href="{calendar_url}" target="_blank" rel="noopener">icj-cij.org &#8599;</a></div>
      </div>
      <div class="updated" id="updated" style="margin-top:22px">Loading data&hellip;</div>
    </div>
  </section>

  <section class="wrap" style="padding-top:28px">
    <div class="feed" id="feed"></div>
  </section>

  <footer class="site-footer">
    <div class="wrap foot-row">
      <div>Hearing dates are drawn from the {abbr} public calendar and can change without notice. Always confirm against the <a href="{calendar_url}" target="_blank" rel="noopener">official source</a> before making plans.</div>
      <div><a href="../index.html">&larr; All courts</a></div>
    </div>
  </footer>

  <script src="../assets/js/site.js"></script>
  <script>ICW.initCourtPage("{slug}");</script>
</body>
</html>
"""


def main():
    out_dir = ROOT / "courts"
    out_dir.mkdir(exist_ok=True)
    for slug, meta in COURTS.items():
        html = TEMPLATE.format(slug=slug, **meta)
        # fix the official-calendar link text to show the real domain
        domain = meta["calendar_url"].split("/")[2]
        html = html.replace("icj-cij.org &#8599;", f"{domain} &#8599;")
        (out_dir / f"{slug}.html").write_text(html)
        print(f"wrote courts/{slug}.html")


if __name__ == "__main__":
    main()
