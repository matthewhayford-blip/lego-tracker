# Retired & Rare — handover

**For:** the next Claude session, or Matt six weeks from now.
**From:** a session ending 6 September 2026.
**Supersedes:** the "Brick Exit" handover of the same date, which is now wrong in
its name, its URLs, its status and its plan.

Read this, then `docs/source-investigation-2026-09-06.md`, then
`research/keyword-data.md`. Everything below is decided unless marked OPEN.

---

## What this is

A **UK LEGO retirement tracker** at **https://retiredandrare.com** — a static site
listing every LEGO set expected to leave shelves in the next twelve months, with UK
prices where we have them and a transparent model of what holding one sealed is worth.
SEO-led, monetised by affiliate commission, later a subscription.

**It is not a LEGO investment dashboard.** See the next section.

## The two things you must not undo

### 1. The framing is retirement and deals, never investment

Real Ahrefs data (`research/keyword-data.md`):

- `lego investment` — **20** UK searches/month. The whole investment vocabulary: ~90.
- The retirement cluster — **~9,540**/month at keyword difficulty **0–7**.
- The deals cluster next door — **~48,000**/month at difficulty 0–17.

Same product, 530:1 difference in audience. The investment model still exists — it is
the differentiator and the basis for the paid tier — but it is never the label on the
tin. If a future prompt drifts back to "investment dashboard", push back and point at
the numbers.

### 2. The site does not claim retirement dates it does not have

This was fixed on 6 September and is easy to undo by accident.

All 343 retirement dates come from one aggregator (Brick Fanatics) and cluster on **two
month-end buckets**: 297 sets on 2026-12-31, 46 on 2027-07-31. They are period
estimates, not per-set announcements. The site previously rendered each one as a precise
day with a countdown — "scheduled to stop production on 31 December 2026, 116 days from
now" — on 297 different pages. That is false precision any knowledgeable LEGO buyer
would catch, and exactly the kind of thing that loses an affiliate application.

Now: `sets.json` carries `date_precision` per set, `date_phrase()` in `site/build.py`
renders a period as a period ("the end of 2026", slug `end-2026`), and copy says
"expected to retire around", naming fan media as the source. `tests/test_dates.py` guards
this — including a test that fails deliberately if the data ever stops being all
estimates, so restoring precise dates is a decision, not a drift.

**If you get genuinely per-set dates, set `date_precision: "exact"` on those sets and
the precise rendering returns automatically.** That is the upgrade path.

## Status

| | |
|---|---|
| Live | **https://retiredandrare.com** — 389 pages, HTTPS enforced |
| Repo | `matthewhayford-blip/lego-tracker` (public) |
| Tests | 27 passing |
| Indexed | **No.** `NOINDEX = True`, `robots.txt` is `Disallow: /` |
| Prices | **11 of 343 sets.** Both scrapers are dead — see below |
| Dates | **2 windows, not 343 dates** |

### Verify it works

```bash
cd repo
pip install -r requirements.txt
pytest -q                     # expect: 27 passed
python site/build.py          # expect: 389 pages
python tools/linkcheck.py     # expect: all internal links resolve
python -m http.server -d public 8000
```

`python site/build.py` works from any directory; `site/build.py` puts the repo root on
`sys.path` itself. It did not, and CI failed on exactly that.

## The blocker: there is no price data, and no route to any

Both phase-1 scrapers were tested against the real internet for the first time on
6 September (the originating sandbox could not reach either host). Both are
**non-viable**, for unrelated reasons. Full evidence in
`docs/source-investigation-2026-09-06.md`.

**lego.com — blocked, not fixable.** 403 Forbidden on the category page, with our own
bot UA *and* with a current desktop Chrome UA. Not user-agent sniffing; a bot-detection
layer. Beating it means fingerprint spoofing and residential proxies, which is the
proxy arms race the project already rejected for Amazon. Do not try to fix this scraper.

**bricktracker.co.uk — fixable, and not worth fixing.** Three real bugs found and
diagnosed (wrong URL pattern; a wrong slug silently serves the homepage rather than
404ing; the multi-retailer prices are in plain HTML, not the JSON-LD the parser reads).
All solvable. But `collector/build_slugmap.py` crawled the site's own theme pages and
found it lists **36 products in total** — of which **7 are ours. 2% coverage.** It is
not a price-comparison database; it is a thin site showing a few current sets per theme.

**Consequence: affiliate product feeds are no longer "phase 2". They are the only route
to price data.** Nothing about the site's core proposition works until one lands.

## Decisions already made — do not relitigate without reason

1. **UK-first.** BrickEconomy is US-centric (UK is 9% of its traffic). UK pricing,
   retailers, GBP, postage and fees is the gap.
2. **343 retiring sets, not the full ~10,000-set catalogue.** Thin pages at scale are a
   ranking risk. Expand only once the 343 rank.
3. **Python + Jinja2, not Astro/Next/Eleventy.** One language across collector, model
   and site. Matt's requirement was "Claude can maintain it when it breaks".
4. **GitHub Actions + GitHub Pages.** When a scraper breaks, source, schedule, logs and
   last good output are all in one repo reachable by `gh`.
5. **Affiliate feeds are the price source.** LEGO's own programme runs on **Rakuten
   Advertising**; most other UK retailers are on **Awin** (£5 refundable deposit).
6. **No Amazon scraping.** Legitimate routes if wanted later: Amazon **Creators API**
   (free, replaced PA-API 5.0) or **Keepa** (€49/mo, gives price *history*).
7. **Sole trader.** UK £1,000 trading allowance covers early revenue.
8. **`NOINDEX = True` until the data is worth indexing.** Not just until the domain was
   final — that has happened. 343 pages of empty price tables would be a bad first
   impression for Google, and the estimate-only dates make it worse.
9. **Every page lives under a market prefix** (`/uk/...`). Added 6 September while
   nothing was indexed, because adding it later costs a site-wide 301. UK is the only
   enabled market and should stay that way until it ranks — this is optionality, not a
   plan.
10. **No monospace, no cream-and-terracotta.** The visual pass deliberately avoids the
    generated-site defaults. Archivo is loaded properly; the previous CSS named IBM Plex
    without ever loading it, so nobody was seeing it.

## Architecture

```
collector/  →  data/  →  site/build.py  →  public/  →  GitHub Pages
  sources      JSON,        Jinja2          static
               committed                     HTML
```

**Everything is server-rendered.** No JavaScript is required to read any content, because
Google has to see the price tables.

**Markets.** `config.MARKETS` holds everything money- or locale-dependent: currency,
symbol, RRP bands for the growth model, selling fee, postage, `lang`, `hreflang`. Nothing
outside `config.py` hardcodes a currency or a fee. Prices are compared only *within* a
market, so a USD quote can never win a GBP comparison. A `us` market is defined but
disabled; it was used to verify the build is genuinely market-agnostic (772 pages, two
markets, all links resolving) and then turned off again.

**Sources prefer JSON-LD over CSS selectors** — but note bricktracker publishes none, so
any new source needs an HTML fallback. Every source implements one method:

```python
class MySource(HttpSource):
    name = "my-source"
    market = "uk"
    currency = "GBP"
    def fetch(self, set_numbers) -> list[PriceQuote]: ...
```

Failure is isolated: a broken source logs a `::warning::` and the site rebuilds from the
last good prices. `data/` is committed on every run, so **price history accumulates in
git for free** — after a few months the growth model can be recalibrated on observed UK
prices instead of a 2015 paper.

**Identity.** `config.OWNER_NAME` and `CONTACT_EMAIL` drive the About/Privacy/Contact
pages. If either starts with `TODO`, the build logs a warning and **skips all three
pages** rather than shipping placeholder identity.

## Traps that already bit us

**Pushing to `main` does not deploy.** `ci.yml` only tests and builds. Only `refresh.yml`
publishes, on a 07:00 daily cron or a manual dispatch. Code changes sit invisible for up
to 24 hours. This caused real confusion twice on 6 September — the site appeared not to
have changed when in fact it had never been deployed. **Worth fixing early:** either add
a deploy step to `ci.yml` or trigger `refresh.yml` on pushes to `main`.

**A full `refresh.yml` run takes ~10 minutes**, because bricktracker is fetched one set
at a time with a politeness delay. It is not hung.

**`{{ rel }}` does not work inside `body_html`.** Those strings are built in Python and
passed through `| safe`, so Jinja never re-renders them. Use a literal relative path.
`tools/linkcheck.py` catches this and runs in CI after the build, so a link that goes
nowhere now fails the run rather than shipping silently.

## OPEN — needs Matt

- **Rotate the GitHub token.** The personal access token used to set this up on
  6 September (`repo` + `workflow` scope) was pasted into a chat window and should be
  treated as compromised. GitHub → Settings → Developer settings → Personal access
  tokens → delete it, and generate a fresh one if a future session needs to push.
  Nothing in the repo depends on it; Actions uses its own `GITHUB_TOKEN`.
- **`hello@retiredandrare.com` does not exist yet.** It is on the live Contact and
  Privacy pages. Cloudflare Email Routing forwards to an existing inbox for free. Do this
  before applying to any network.
- **Repo is still named `lego-tracker`.** Harmless on a custom domain; rename if you want
  it tidy.
- **Better retirement dates.** The single highest-value data upgrade. Two windows makes
  `/retiring/end-2026/` a 297-set dump, kills the countdown as a hook, and forfeits the
  date-bound long-tail queries the whole SEO plan was built on.

## What to do next, in order

1. **Rotate the exposed GitHub token** (see OPEN). Two minutes.
2. **Set up the contact email.** Small, blocking, five minutes.
3. **Fix the deploy trigger** so pushing to `main` publishes.
4. **Apply to Rakuten (LEGO) and Awin (Argos, John Lewis, Very, Zavvi).** There is now a
   live site on a real domain with About, Privacy and Contact — which is what they check.
   Expect the thin price data to be the weak point of the application.
5. **Write `awin.py` and `rakuten.py` as approvals land; delete the scrapers.**
6. **Improve the retirement dates** (may run in parallel with 4–5).
7. **Lift `NOINDEX`**, verify in Search Console, submit `sitemap.xml` — only once the
   price tables and dates are worth showing.
8. **Build the deals pages** (`/deals/*`) — the ~48,000/month cluster.
9. **Only then:** `/tracker` interactivity and the paid tier.

Running throughout, and more important than any of it: **links**. See the bottleneck
section in `research/keyword-data.md`. A technically excellent site nobody links to gets
60 visits a month — that is measured, not theoretical.

## Set expectations honestly

By week four there will be an excellent site nobody visits, and it will stay that way for
months. That is how SEO behaves. Month six is the earliest the traffic data means
anything. Say so rather than letting it read as failure.

## Diagnostic tooling

`collector/debug_fetch.py` and `.github/workflows/debug-fetch.yml` fetch a real page from
a source in CI and commit the HTML plus a JSON-LD summary to `data/debug/`, so a source
can be inspected from an environment that cannot reach it. This is the fastest way to
diagnose a broken parser and is worth keeping. `collector/build_slugmap.py` is
bricktracker-specific and can be deleted with that source.
