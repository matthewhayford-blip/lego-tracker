# Price source investigation — 6 September 2026

First real-network test of the phase-1 scrapers, run from GitHub Actions
(the originating sandbox could not reach these hosts). Both sources were
written from observed page structure and had never made a live request.

**Conclusion: neither phase-1 scraper is viable. Phase 2 (affiliate product
feeds) is not an upgrade — it is the only route to real price data.**

---

## lego.com — blocked, not fixable

`GET https://www.lego.com/en-gb/categories/retiring-soon` returns **403
Forbidden**, after 3 attempts, with:

- our honest `BrickExitBot/0.1` UA — 403
- a current desktop Chrome UA — 403

Same result both ways, so this is not user-agent sniffing. It is a bot
detection / WAF layer, and getting past it means fingerprint spoofing,
residential proxies and an ongoing arms race. That is precisely the reason
the original handover rejected Amazon scraping (decision 6), and the same
reasoning applies here with equal force.

Also noted: the URL in `lego_com.py` is stale. `/categories/retiring-soon`
now canonicalises to `/categories/last-chance-to-buy`. Irrelevant while the
403 stands, but worth knowing if the official feed ever needs cross-checking.

**Action: do not attempt to fix this scraper.** LEGO's own affiliate
programme runs on Rakuten Advertising (Product Search API + catalog feeds) —
that is the supported, contractual way to get LEGO's UK prices, and it was
already the plan.

## bricktracker.co.uk — reachable, parseable, and far too small

Three separate problems were found, in order:

1. **Wrong URL pattern.** `SET_URL` is `/set/{set_number}`, which 404s.
   The real pattern is `/lego-sets/<slug>-<set_number>`, e.g.
   `/lego-sets/lego-star-wars-millennium-falcon-75192`.

2. **A wrong URL fails silently.** `/lego-sets/75192` and
   `/lego-sets/x-75192` both return HTTP 200 serving the *homepage*, not a
   404. Any slug-guessing strategy would therefore appear to work while
   producing garbage. There is no `robots.txt` and no `sitemap.xml`.

3. **The multi-retailer prices are not in JSON-LD.** With the correct URL
   there is exactly one JSON-LD `Product` node, whose single `Offer` carries
   an aggregate price and no seller name. The actual per-retailer table
   (Amazon, Argos, Smyths, John Lewis, Hamleys, Tesco, OnBuy, Asda) lives in
   plain HTML: `div.product-latest-price` containing `div.merchant-name` and
   `div.merchant-price`. Many rows are "Check" placeholders with no price at
   all. `bricktracker.py` has no HTML fallback, so it could never have read
   this even with the right URL.

### The finding that settles it

`collector/build_slugmap.py` was written to solve problem 1+2 properly, by
crawling `/themes` and reading the slugs the site publishes itself. It works.
The result (`data/bricktracker_slugs.json`, run 2026-09-06):

| | |
|---|---|
| Themes crawled | ~50 |
| **Total products listed on the entire site** | **36** |
| Our tracked retiring sets | 343 |
| **Coverage of our sets** | **7 (2.0%)** |

bricktracker.co.uk is not a broad UK price-comparison database. It lists a
handful of current, mostly new sets per theme. It has almost no coverage of
retiring or older sets — which is the entire subject of this project.

Even fully repaired, this source would price 2% of the catalogue. The parser
work is not worth doing.

---

## What this means for the plan

- The 11 `research-seed` prices in `data/prices/current.json` remain the only
  real UK price data in the repo.
- Affiliate feeds move from "phase 2" to "the critical path". Nothing about
  the site's core value proposition — live UK prices — works until one lands.
- Applications need a live site on a real domain, which makes **the name and
  domain decision the true blocker for the whole project**, not a tidy-up
  task.
- `NOINDEX` should stay `True` meanwhile. Shipping 343 pages whose price
  tables are near-empty would be a bad first impression for Google.

### Files from this investigation

| Path | |
|---|---|
| `collector/debug_fetch.py` | one-off diagnostic capture; keep for re-testing a source |
| `collector/build_slugmap.py` | bricktracker theme crawler; retain as evidence / if the site ever grows |
| `data/bricktracker_slugs.json` | the 36 slugs found |
| `data/debug/` | captured real HTML + JSON-LD summaries |
| `.github/workflows/debug-fetch.yml`, `slugmap.yml` | manual triggers for the above |

These are diagnostic tools, not pipeline code. Delete them once the feed
sources exist, or keep `debug_fetch.py` as the standard way to inspect a
source from CI when it breaks.
