# Retired & Rare — UK LEGO retirement tracker

A static site that tracks every LEGO set retiring in the next twelve months,
with live UK prices and a transparent model of what holding one sealed is worth.

**386 pages**, generated nightly from live data. No JavaScript is required to
read any content — Google has to see the price tables.

## How it works

```
collector/  →  data/  →  site/build.py  →  public/  →  GitHub Pages
  (sources)    (JSON,      (Jinja2)         (static
               committed)                    HTML)
```

The nightly workflow collects prices, rebuilds every page, commits the data, and
deploys. Committing `data/` on every run means **the price history accumulates in
git for free** — after a few months the growth model can be recalibrated on our own
observed UK prices instead of a 2015 academic paper.

## Commands

```bash
pip install -r requirements.txt

python -m collector.run              # collect prices into data/
python -m collector.run --limit 5    # smoke test against 5 sets
python -m collector.run --only lego.com
python site/build.py                 # data/ -> public/
pytest -q                            # 14 tests, no network
python -m http.server -d public 8000
```

## Adding a price source

Write one class with one method. Nothing downstream knows where a quote came from.

```python
class MySource(HttpSource):
    name = "my-source"
    market = "uk"          # which market's prices this returns
    currency = "GBP"
    def fetch(self, set_numbers) -> list[PriceQuote]: ...
```

Register it in `collector/sources/__init__.py`. This is how phase 2 swaps scraped
aggregators for Awin and Rakuten affiliate product feeds: add two files, delete two,
change nothing else.

**Prefer JSON-LD over CSS selectors.** `extract_json_ld()` in `sources/base.py`
reads the `schema.org` data retailers publish for search engines. They keep it
stable and correct across redesigns, which is exactly the breakage a
selector-based scraper suffers.

## Markets

Every page lives under a market prefix — `/uk/retiring/2026/`, never
`/retiring/2026/`. The prefix exists from day one because adding it after URLs
are indexed costs a site-wide 301 and a ranking dip; adding a market now costs a
config entry.

The site is **UK-first and should stay that way until the UK ranks.** The
multi-market plumbing is optionality, not a plan to use it soon — see the
handover on why UK-only is the differentiator.

`config.MARKETS` holds everything money- or locale-dependent: currency and
symbol, RRP bands for the growth model, marketplace selling fee, postage
floor/cap/rate, `lang` and `hreflang`. Nothing outside `config.py` should
hardcode a currency, a fee or a locale.

To add a market:

1. Add an entry to `config.MARKETS` with `"enabled": True`.
2. Give sets an RRP for it in `data/sets.json` under `rrp.<market>`. Sets
   without one are skipped for that market rather than mispriced.
3. Add a price source whose `market`/`currency` match.

Prices are only ever compared *within* a market — `best_per_set()` groups by
market first, so a cheaper USD number can never win a GBP comparison.

The site root `/` is a noindex meta-refresh to the default market. GitHub Pages
cannot issue a real 301, so this is the available approximation; crawlers are
pointed at `/<market>/` by canonical, hreflang and the sitemap.

## Checks

```bash
pytest -q                  # unit tests
python site/build.py       # must succeed from any directory
python tools/linkcheck.py  # every internal link must resolve
```

All three run in CI on every push. The link check exists because a wrong relative
path renders fine and silently 404s; it has already caught two real bugs.

## When a source breaks

It will — that is what scrapers do, and why phase 2 moves to affiliate feeds.

1. The nightly run posts a `::warning::` naming the failed source. The site still
   rebuilds from the last good prices, so **a broken scraper never takes the site down**.
2. Open the failed step's log. `SourceError` messages say which URL and what was
   expected.
3. Save the live HTML into `tests/fixtures/`, add a case to `tests/test_sources.py`,
   fix the parser until it passes.

The `smoke-sources` CI job hits the real sources on every push and is allowed to
fail — its job is to warn, not to block a merge.

## Before launch

- [ ] Set `DOMAIN` in `config.py`
- [ ] Set `NOINDEX = False` — this also switches `robots.txt` from `Disallow: /`
- [ ] Apply to Rakuten (LEGO) and Awin (Argos, John Lewis, Very, Zavvi)
- [ ] Set `AFFILIATE_ACTIVE = True` once links are monetised — ASA requires disclosure
- [ ] Add privacy and cookie pages
- [ ] Verify in Google Search Console, submit `sitemap.xml`

## Layout

| Path | What it is |
|---|---|
| `config.py` | brand, domain, noindex — rename the project here and nowhere else |
| `collector/sources/base.py` | the `PriceSource` interface and shared HTTP/JSON-LD helpers |
| `model/growth.py` | the CAGR model, with its calibration documented in the docstring |
| `site/build.py` | data + templates → 386 pages, sitemap, robots |
| `data/prices/history/` | one snapshot per run, forever |

Data licence: retirement dates compiled from public fan media (Brick Fanatics,
Brickfact). Prices observed from public retail pages. Not affiliated with the LEGO Group.
