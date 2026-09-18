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
.github/workflows/      The daily scrape-and-commit job
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
   the daily job can commit the refreshed data.

## Running the scraper locally

```bash
cd scrapers
pip install -r ../requirements.txt
playwright install chromium
python run_all.py
```

That `playwright install chromium` step only needs to run once (or
again after a `playwright` version bump) — it downloads the actual
browser binary, which the `playwright` pip package alone does not
include. Skipping it will make `icc.py`/`ksc.py` fail with a clear
"executable doesn't exist" error telling you to run it.

This rewrites `data/hearings.json` (and `data/itlos-news.json`) in
place. Run an individual scraper on its own to debug it, e.g.
`python echr.py` — each module prints its own JSON when run directly.

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
- **ICC is now fully working**, rewritten against real markup the
  user pasted directly (not guessed): it's FullCalendar.js, each
  week is a `.fc-content-skeleton` table with a `<thead>` row giving
  each day's exact `data-date` attribute and a `<tbody>` row in the
  same column order with the actual hearings — matched by position
  via `zip()`, so no month-rollover guessing is needed (unlike KSC's
  grid, which doesn't expose dates this directly). Bonus: hearing
  color-classes map back to a courtroom via the page's own "Courtroom
  I/II/III" legend, so `location` includes which courtroom. Verified
  against the real snippet the user shared — parsed both example
  hearings ("El Hishri (Libya)", "Abd-Al-Rahman (Darfur, Sudan)")
  with correct dates, times, and courtrooms.
- **KSC**: a real headless browser gets a Cloudflare-style "performing
  security verification" challenge page instead of the calendar —
  confirmed by inspecting the live output directly. This is a
  fundamentally harder problem than anything else on this list: it's
  not a missing fingerprint or un-rendered JS, it's active detection
  of the automated browser itself. `_scrape_month` now waits longer
  (7s) on the chance a non-interactive challenge clears on its own,
  and reports clearly when it's still stuck on the challenge page
  rather than misreporting it as "no table found". If the longer wait
  doesn't clear it, further options (stealth-patched browser
  automation, CAPTCHA-solving services) exist but amount to an
  escalating arms race against a security product built to resist
  exactly that — `data/manual/ksc.json` is the sensible stopping
  point at that stage, not a consolation prize.
- **WTO**: found a real entry (1 DSB meeting) on the first run with
  working JS rendering — the row-matching logic is doing its job,
  though with only one data point so far it's still the
  least-battle-tested scraper of the seven. Worth a skim of
  `courts/wto.html` to confirm that entry looks like a genuine
  meeting and not a false match.
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
  includes the markup for courts that have it. First real run against
  the live page found 0 items (worked fine on synthetic test markup,
  so the assumption about which tag wraps each item's date was wrong)
  — widened to match a date in any short leaf tag (p/span/div/time),
  not just `<p>`, and now dumps debug HTML on a 0-item result too;
  worth confirming this actually fixed it on the next run.
- **KSC**'s month-grid parsing (which cells belong to the
  previous/next month) was verified against a real July 2026 page
  layout, so that part should be solid once the 403 above is cleared.

If a scraper ever comes up empty without a clear reason again, check
`scrapers/.debug/<court>.html` (see `base.dump_debug`) before
guessing — it's the literal response the scraper received.

None of these will break the site — a scraper that fails or finds
nothing just leaves that court's last-known data in place (see
`base.replace_court`).
