# Brick Exit — UK LEGO retirement tracker

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
    def fetch(self, set_numbers) -> list[PriceQuote]: ...
```

Register it in `collector/sources/__init__.py`. This is how phase 2 swaps scraped
aggregators for Awin and Rakuten affiliate product feeds: add two files, delete two,
change nothing else.

**Prefer JSON-LD over CSS selectors.** `extract_json_ld()` in `sources/base.py`
reads the `schema.org` data retailers publish for search engines. They keep it
stable and correct across redesigns, which is exactly the breakage a
selector-based scraper suffers.

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
