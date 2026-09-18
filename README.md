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

## Known rough edges

- **ICC** (`scrapers/icc.py`): the calendar page returned a
  bot-detection block during initial testing. It may behave
  differently from GitHub's Actions runners — check the workflow logs
  after the first scheduled run. If it keeps failing, use
  `data/manual/icc.json` as a stopgap.
- **WTO** (`scrapers/wto.py`): the official calendar is a JS-driven
  filter widget over a general meetings list; the scraper reads the
  server-rendered list and filters by text match, which is the
  least-tested of the six scrapers.
- **IACtHR** (`scrapers/iacthr.py`): this court publishes session
  date ranges rather than individual hearings, so entries read as
  "192nd Regular Session, through 3 Jul" rather than a case name.
- **KSC** (`scrapers/ksc.py`): this one's a month-grid calendar
  (`?calendar_timestamp=YYYY-MM`) rather than a flat list, so the
  scraper has to guess which grid cells spill over from the
  previous/next month based on row position — verified against a
  real July 2026 page, but worth double-checking against the live
  site after the first run.

None of these will break the site — a scraper that fails or finds
nothing just leaves that court's last-known data in place (see
`base.replace_court`).
