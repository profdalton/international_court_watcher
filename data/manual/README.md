Drop a `<slug>.json` file here (e.g. `icc.json`) with an array of
hearing records in the same shape scrapers/base.py documents, and
run_all.py will merge them into data/hearings.json on the next run —
useful for courts whose scraper is struggling (ICC and WTO, most
likely) until the selector is fixed.
