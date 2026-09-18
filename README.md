# International Court Watcher

A single, plain-language calendar of upcoming hearings and sessions at
seven international tribunals — the ICJ, ICC, ECHR, IACtHR, ITLOS,
the Kosovo Specialist Chambers, and the WTO Dispute Settlement Body —
pulled from each court's own public calendar and republished as one
static site.

Live at **internationalcourtwatcher.com**.

## How it's built

Same shape as the De Novo (T14 journal tracker) project: a static
site with no build step, kept current by a Python scraper that runs
on a GitHub Actions schedule and commits straight to `main`.

```
index.html            Homepage: unified feed + court grid
about.html
courts/<slug>.html     One page per tribunal (generated — see below)
assets/                CSS, JS, logo/favicon
data/courts.json       Static metadata about each tribunal
data/hearings.json     The live data — rewritten by the scraper
data/manual/           Hand-entered overrides, merged in on top
scrapers/               Python scraper, one module per court
.github/workflows/      The weekly scrape-and-commit job
```

The front end (`assets/js/site.js`) fetches `data/hearings.json` and
`data/courts.json` client-side and renders the feed — there's nothing
to compile or deploy beyond pushing the files.

## Local setup

1. **Publish on GitHub Pages.** Push this repo, then in *Settings →
   Pages* set the source to the `main` branch, root folder. The
   `CNAME` file is already set to `internationalcourtwatcher.com`.
2. **Point the domain at GitHub Pages.** At your registrar, add:
   - Four `A` records for the apex (`internationalcourtwatcher.com`)
     pointing at GitHub's Pages IPs (185.199.108.153,
     185.199.109.153, 185.199.110.153, 185.199.111.153), or a `ALIAS`/
     `ANAME` record if your registrar supports one instead.
   - A `CNAME` record for `www` pointing at
     `<your-github-username>.github.io`, if you want the `www`
     subdomain to work too.
   Then in *Settings → Pages*, enter the custom domain and enable
   "Enforce HTTPS" once it's verified (can take a few hours).
3. **Let Actions push commits.** Under *Settings → Actions → General
   → Workflow permissions*, select "Read and write permissions" so
   the weekly job can commit the refreshed data.

## Running the scraper locally

```bash
cd scrapers
pip install -r ../requirements.txt
python run_all.py
```

This rewrites `data/hearings.json` in place. Run an individual
scraper on its own to debug it, e.g. `python echr.py` — each module
prints its own JSON when run directly.

## Adding a court

1. Add an entry to `data/courts.json` (name, seat, blurb, calendar
   URL, an accent color, etc.).
2. Write `scrapers/<slug>.py` with a `scrape()` function returning
   records in the shape documented at the top of `scrapers/base.py`.
3. Register it in `SCRAPERS` in `scrapers/run_all.py`.
4. Run `python scrapers/generate_pages.py` to generate
   `courts/<slug>.html`.

If a court doesn't publish a real forward-looking hearings calendar
(only a news/press feed, like ITLOS), skip step 2 and instead follow
`scrapers/itlos_news.py` as a template: write to its own
`data/<slug>-news.json` rather than `data/hearings.json`, and add
`news_file`/`news_source_url` to its `data/courts.json` entry so
`generate_pages.py` includes the "Recent announcements" section.

## Known rough edges

Confirmed from real local runs (see terminal output for the exact
messages) — all of this fails safe: a broken court just keeps its
last-known data (`base.replace_court`), it doesn't blank the page.

- **Fixed:** ICJ, ITLOS, and IACtHR all came back empty in testing —
  not because of their marker text or regexes, but because
  `base.HEADERS` claimed Brotli (`br`) compression support that
  wasn't actually installed. The servers sent Brotli-compressed
  bodies that never got decoded, and `resp.text` returned raw
  compressed bytes read as garbage text. Fixed by no longer
  overriding `Accept-Encoding` — `requests` picks a safe default on
  its own. Worth a re-run to confirm all three parse correctly now.
- **ICC** and **KSC** both come back `403 Forbidden`, even with a
  full browser-style header set and retries — unrelated to the
  Brotli bug above. That rules out a bare User-Agent block — it's a
  WAF doing something requests can't clear on its own (IP reputation,
  a JS/cookie challenge, or TLS fingerprinting). Realistic next step
  for either is a headless-browser fetch (Playwright/Selenium)
  instead of `requests`, which isn't wired in by default since it's a
  heavier dependency; in the meantime, `data/manual/icc.json` and
  `data/manual/ksc.json` are the stopgap.
- **WTO**: the official calendar is a JS-driven filter widget over a
  general meetings list; the scraper reads the server-rendered list
  and filters by text match. It found 0 DSB rows in testing — check
  whether "Dispute Settlement Body" actually appears in the
  server-rendered HTML at all, or whether the list only populates via
  JS.
- **IACtHR**: session date ranges rather than individual hearings
  ("192nd Regular Session, through 3 Jul" rather than a case name).
- **ITLOS**'s hearings feed being empty is usually *correct*, not
  broken — this tribunal only publishes a Schedule of Hearings entry
  when something is actually scheduled, which is rare. What it
  publishes regularly instead is a general press/news feed (workshops,
  judge elections, case orders, the occasional hearing announcement,
  all mixed together with no structural way to tell them apart). Since
  regexing "hearing" out of free-form news text would just produce
  false positives, `scrapers/itlos_news.py` doesn't try — it pulls the
  most recent items as plain announcements into their own
  `data/itlos-news.json`, kept separate from `data/hearings.json` so
  it can never pollute the cross-court feed or hearing counts.
  `courts/itlos.html` shows them in a clearly-labeled "Recent
  announcements" section, distinct from the hearings feed above it. A
  court gets this section by adding `news_file` (and `news_source_url`)
  to its `data/courts.json` entry — `scrapers/generate_pages.py` only
  includes the markup for courts that have it.
- **KSC**'s month-grid parsing (which cells belong to the
  previous/next month) was verified against a real July 2026 page
  layout, so that part should be solid once the 403 above is cleared.

If a scraper ever comes up empty without a clear reason again, check
`scrapers/.debug/<court>.html` (see `base.dump_debug`) before
guessing — it's the literal response the scraper received.

None of these will break the site — a scraper that fails or finds
nothing just leaves that court's last-known data in place (see
`base.replace_court`).
