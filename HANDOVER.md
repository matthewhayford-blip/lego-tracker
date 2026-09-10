# Retired & Rare: handover

**For:** the next Claude session, or Matt tomorrow.
**From:** a session ending 7 September 2026.
**Supersedes:** the handover of 6 September, which is now wrong on status (the deploy
trigger it flagged as broken is fixed, and the homepage it described no longer exists)
and needs today's design and voice work folded in.

Read this, then `docs/source-investigation-2026-09-06.md`, then
`research/keyword-data.md`. Everything below is decided unless marked OPEN.

Writing any site copy? Read `docs/tone-of-voice.md` first.

---

## What this is

A **UK LEGO retirement tracker** at **https://retiredandrare.com**, a static site
listing every LEGO set expected to leave shelves in the next twelve months, with UK
prices where we have them and a transparent model of what holding one sealed is worth.
SEO-led, monetised by affiliate commission, later a subscription.

**It is not a LEGO investment dashboard.** See the next section.

## The three things you must not undo

### 1. The framing is retirement and deals, never investment

Real Ahrefs data (`research/keyword-data.md`):

- `lego investment`: **20** UK searches/month. The whole investment vocabulary: ~90.
- The retirement cluster: **~9,540**/month at keyword difficulty **0-7**.
- The deals cluster next door: **~48,000**/month at difficulty 0-17.

Same product, 530:1 difference in audience. The investment model still exists (it is
the differentiator and the basis for the paid tier), but it is never the label on the
tin. If a future prompt drifts back to "investment dashboard", push back and point at
the numbers.

### 2. The site does not claim retirement dates it does not have

All 343 retirement dates come from one aggregator (Brick Fanatics) and cluster on **two
month-end buckets**: 297 sets on 2026-12-31, 46 on 2027-07-31. They are period
estimates, not per-set announcements.

`sets.json` carries `date_precision` per set, `date_phrase()` in `site/build.py`
renders a period as a period ("the end of 2026", slug `end-2026`), and copy says
"expected to retire around", naming fan media as the source, never a precise day or a
countdown. `tests/test_dates.py` guards this, including a test that fails deliberately
if the data ever stops being all estimates, so restoring precise dates is a decision,
not a drift.

**If you get genuinely per-set dates, set `date_precision: "exact"` on those sets and
the precise rendering returns automatically.** That is the upgrade path.

### 3. No em dashes, and the rest of the tone-of-voice guide

New today, and just as easy to drift on as the first two. `docs/tone-of-voice.md` is
the full guide (five traits, before/after examples, a self-edit checklist); the one
rule enforced hardest is no em dashes anywhere in site copy, ever. The guide's own
first draft had eighteen of them before a re-read caught it, so check your own work
rather than assuming a careful first pass got it right.

## Status

| | |
|---|---|
| Live | **https://retiredandrare.com**, 394 pages, HTTPS enforced |
| Repo | `matthewhayford-blip/lego-tracker` (public) |
| Tests | 27 passing |
| Indexed | **No.** `NOINDEX = True`, `robots.txt` is `Disallow: /` |
| Prices | **11 of 343 sets.** Both scrapers are dead, see below |
| Dates | **2 windows, not 343 dates** |
| Homepage | Redesigned today (Field Notes direction). Every other page is still the old brass/paper look, see below |

### Verify it works

```bash
cd repo
pip install -r requirements.txt
pytest -q                     # expect: 27 passed
python site/build.py          # expect: 394 pages
python tools/linkcheck.py     # expect: all internal links resolve
python -m http.server -d public 8000
```

`python site/build.py` works from any directory; `site/build.py` puts the repo root on
`sys.path` itself.

## What happened today: homepage redesign and a tone-of-voice guide

Three PRs, in order:

- **#1, deploy fix.** Merged. Pushing to `main` used to sit undeployed until the next
  06:00 UTC refresh cron; it now deploys on every push. See "Traps that already bit us"
  below for the mechanism and where to check if it ever stops working again.
- **#2, homepage redesign.** The homepage was mocked up in a Claude Design canvas
  (`https://claude.ai/code/artifact/7e92a3f0-a6a1-4fcf-93a6-aaa7d157984d`, if it's still
  live) across several rounds: an "Elevated & Considered" brass/paper direction that
  Matt rejected outright as looking like a directory with no personality, then a
  wireframe pass to settle the structure (hero, ticker, one spotlighted set instead of
  a grid, browse by theme, browse by price, a retired-sets teaser, the retirement
  calendar), then two visual directions on top of that structure. Matt picked "Field
  Notes" (deep green, cream, mustard-gold, a Space Grotesk display face) over "Drop
  Calendar" (dark, marketplace-bold). Merged, and it is real, working code, not just a
  mockup:
  - the spotlight set and ticker use the site's real `featured` set list, and the
    5-year modelled value on the homepage is computed identically to the set page's
    own model (both show the Millennium Falcon at £1,433, because it's the same call)
  - `retiring/price/<bracket>/` is a new set of real hub pages (five brackets, grouped
    from `mkt["rrp_bands"]`, the same thresholds the growth model already uses rather
    than a second set of magic numbers), linked from both the homepage and `/retiring/`
  - the "Already retired" section is an honest coming-soon teaser with **no invented
    numbers**. There is no secondary-market data source yet (see OPEN below), and this
    site does not publish guessed prices dressed up as data. Worth knowing: the first
    draft of that teaser named specific "already retired" sets from memory, and one of
    them (Hogwarts Castle, 71043) turned out on a quick check to still be in production
    and one of this site's *own* tracked retiring-soon sets. Don't name specific sets
    as retired without a real, checked source.
  - the "Notify me" signup from the mockup was **not** built. There is no email-capture
    backend (this is a static GitHub Pages site), and a fake form is worse than no form.
  - **only the homepage changed.** Every other page (set pages, tracker, hub, waves,
    themes, price brackets, about/privacy/contact/method) still has the old brass/paper
    look. Carrying the Field Notes direction to the rest of the site is open, below.
- **#3, tone-of-voice guide.** `docs/tone-of-voice.md` plus a homepage copy pass against
  it. Merged. Applying the guide to the homepage also caught two em dashes baked into
  shared chrome (the `<title>` separator and the footer tagline), which were on every
  page, not just the homepage. Both fixed.

## The blocker: there is no price data, and no route to any

Both phase-1 scrapers were tested against the real internet for the first time on
6 September. Both are **non-viable**, for unrelated reasons. Full evidence in
`docs/source-investigation-2026-09-06.md`.

**lego.com, blocked, not fixable.** 403 Forbidden on the category page, with our own
bot UA *and* with a current desktop Chrome UA. Not user-agent sniffing; a bot-detection
layer. Beating it means fingerprint spoofing and residential proxies, which is the
proxy arms race the project already rejected for Amazon. Do not try to fix this scraper.

**bricktracker.co.uk, fixable, and not worth fixing.** Three real bugs found and
diagnosed (wrong URL pattern; a wrong slug silently serves the homepage rather than
404ing; the multi-retailer prices are in plain HTML, not the JSON-LD the parser reads).
All solvable. But `collector/build_slugmap.py` crawled the site's own theme pages and
found it lists **36 products in total**, of which **7 are ours: 2% coverage.** It is
not a price-comparison database; it is a thin site showing a few current sets per theme.

**Consequence: affiliate product feeds are no longer "phase 2". They are the only route
to price data,** and, now, to any real secondary-market data for the retired-sets
section too. Nothing about the site's core proposition works until one lands.

## Decisions already made, do not relitigate without reason

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
   final, that has happened. 343 pages of empty price tables would be a bad first
   impression for Google, and the estimate-only dates make it worse.
9. **Every page lives under a market prefix** (`/uk/...`). UK is the only enabled
   market and should stay that way until it ranks; this is optionality, not a plan.
10. **No monospace, no cream-and-terracotta.** Still true, and now also: no brass and
    parchment on the homepage (that was the rejected "directory" look), Field Notes
    instead.
11. **The homepage's structure is Wireframe B, not a shop grid.** One spotlighted set,
    not a 4-up product grid; a horizontal browse row for themes and for price brackets,
    not a tile wall. Matt's call after seeing both wireframes side by side.
12. **No em dashes anywhere in site copy.** See `docs/tone-of-voice.md`.

## Architecture

```
collector/  ->  data/  ->  site/build.py  ->  public/  ->  GitHub Pages
  sources        JSON,        Jinja2          static
                 committed                     HTML
```

**Everything is server-rendered.** No JavaScript is required to read any content,
because Google has to see the price tables.

**Markets.** `config.MARKETS` holds everything money- or locale-dependent: currency,
symbol, RRP bands for the growth model, selling fee, postage, `lang`, `hreflang`.
Nothing outside `config.py` hardcodes a currency or a fee. Prices are compared only
*within* a market, so a USD quote can never win a GBP comparison. A `us` market is
defined but disabled.

**Sources prefer JSON-LD over CSS selectors,** but note bricktracker publishes none, so
any new source needs an HTML fallback. Every source implements one method:

```python
class MySource(HttpSource):
    name = "my-source"
    market = "uk"
    currency = "GBP"
    def fetch(self, set_numbers) -> list[PriceQuote]: ...
```

Failure is isolated: a broken source logs a `::warning::` and the site rebuilds from
the last good prices. `data/` is committed on every run, so **price history
accumulates in git for free**, after a few months the growth model can be recalibrated
on observed UK prices instead of a 2015 paper.

**Identity.** `config.OWNER_NAME` and `CONTACT_EMAIL` drive the About/Privacy/Contact
pages. If either starts with `TODO`, the build logs a warning and **skips all three
pages** rather than shipping placeholder identity. Both values are set in `config.py`,
but nobody has confirmed the `hello@retiredandrare.com` inbox actually receives mail
yet, see OPEN below.

**Homepage-only styling.** `site/static/home.css` and the `Space Grotesk` font are
loaded only on `/`, via `base.html`'s `head_extra` block, and every home.css rule is
scoped under `body.home-v2` (set by `home.html`'s `body_class` block). This was
deliberate so the redesign couldn't leak onto any other page by accident. Extending
the Field Notes look to another page means giving it the same `body_class` and writing
that page's own scoped CSS, not editing `style.css` directly.

## Traps that already bit us

**Pushing to `main` used to not deploy, fixed 7 September.** `ci.yml` now has a `deploy`
job that runs after `test` passes on a push to `main`: it rebuilds the site from
whatever is already committed in `data/` (it does not run the collector) and publishes
it via `actions/deploy-pages`. `refresh.yml` is unchanged and still owns fetching new
prices on its 06:00 UTC cron. Both `deploy` jobs share the `pages` concurrency group so
a code push and a scheduled refresh can't race each other; GitHub's `github-pages`
environment serializes them further on its own. If a push to `main` still doesn't show
up on the site, check the `deploy` job in the `ci` workflow run, not `refresh`.

**A full `refresh.yml` run takes ~10 minutes,** because bricktracker is fetched one set
at a time with a politeness delay. It is not hung.

**`{{ rel }}` does not work inside `body_html`.** Those strings are built in Python and
passed through `| safe`, so Jinja never re-renders them. Use a literal relative path.
`tools/linkcheck.py` catches this and runs in CI after the build, so a link that goes
nowhere now fails the run rather than shipping silently.

**A cloud Claude session may not have push access to this repo.** This bit today's
session: local commits sat unpushed, and every change had to go out as a `git
format-patch` handed to a separately-authorized Claude Code session to `git am` and
push. If this happens again: don't try to work around it (no force, no alternate
remote); generate the patch, verify it applies cleanly against the *current* `origin/main`
(`git fetch` and read access usually still work even when push doesn't), and hand it to
a session that has real access. Paste patch text directly if file attachments don't
reach that session; they land in the human's chat, not in another Claude session's
environment.

## OPEN, needs Matt

- **Rotate the GitHub token.** The personal access token used to set this up on
  6 September (`repo` + `workflow` scope) was pasted into a chat window and should be
  treated as compromised. GitHub, Settings, Developer settings, Personal access
  tokens, delete it, and generate a fresh one if a future session needs to push.
  Nothing in the repo depends on it; Actions uses its own `GITHUB_TOKEN`. Still not
  done as of 7 September.
- **Confirm `hello@retiredandrare.com` actually receives mail.** It is on the live
  Contact and Privacy pages and set in `config.py`, but nobody has verified the
  Cloudflare Email Routing forwarding is actually in place. Do this before applying to
  any affiliate network, they will use this address.
- **Rakuten and Awin applications.** Still not started. This is the actual
  critical-path blocker, for the retiring-soon prices and now for any real
  "already retired" secondary-market data too. See "What to do next" below.
- **Repo is still named `lego-tracker`.** Harmless on a custom domain; rename if you
  want it tidy.
- **Better retirement dates.** The single highest-value data upgrade. Two windows
  makes `/retiring/end-2026/` a 297-set dump, kills the countdown as a hook, and
  forfeits the date-bound long-tail queries the whole SEO plan was built on.
- **Whether to build the "Already retired" section for real.** It needs a genuinely
  new data source (eBay sold + active listings, BrickLink), which is closer to the
  investment framing this project deliberately avoids. Flagged, not decided.
- **Whether to carry Field Notes to the rest of the site**, and on what timeline. The
  homepage and every other page currently look like two different sites.

## What to do next, in order

1. **Rotate the exposed GitHub token** (see OPEN). Two minutes.
2. **Confirm the contact email actually forwards** (see OPEN). Five minutes.
3. **Apply to Rakuten (LEGO) and Awin (Argos, John Lewis, Very, Zavvi).** There is now
   a live site on a real domain with About, Privacy and Contact, which is what they
   check. Expect the thin price data to be the weak point of the application.
4. **Write `awin.py` and `rakuten.py` as approvals land; delete the scrapers.**
5. **Improve the retirement dates** (may run in parallel with 3-4).
6. **Decide on the rest of the visual pass**: carry Field Notes to set pages, the
   tracker, and the hub pages, or leave them as-is until a bigger content push.
7. **Lift `NOINDEX`**, verify in Search Console, submit `sitemap.xml`, only once the
   price tables and dates are worth showing.
8. **Build the deals pages** (`/deals/*`), the ~48,000/month cluster.
9. **Only then:** `/tracker` interactivity and the paid tier.

Running throughout, and more important than any of it: **links**. See the bottleneck
section in `research/keyword-data.md`. A technically excellent site nobody links to
gets 60 visits a month, that is measured, not theoretical.

## Set expectations honestly

By week four there will be an excellent site nobody visits, and it will stay that way
for months. That is how SEO behaves. Month six is the earliest the traffic data means
anything. Say so rather than letting it read as failure.

## Diagnostic tooling

`collector/debug_fetch.py` and `.github/workflows/debug-fetch.yml` fetch a real page
from a source in CI and commit the HTML plus a JSON-LD summary to `data/debug/`, so a
source can be inspected from an environment that cannot reach it. This is the fastest
way to diagnose a broken parser and is worth keeping. `collector/build_slugmap.py` is
bricktracker-specific and can be deleted with that source.
