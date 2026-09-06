#!/usr/bin/env python3
"""Turn data/ into a static site of pre-rendered pages.

Every page ships complete HTML: no JavaScript is required to read any content,
because Google has to see the price tables.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

# Running this file directly (`python site/build.py`, as CI and the README do)
# puts this file's own directory on sys.path, not the repo root -- so the
# repo-root imports below (config, collector, model) fail with
# ModuleNotFoundError unless the root is added explicitly first. Doing it here
# means the script works regardless of how or from where it's invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from collector import normalise
from model import growth as G

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
log = logging.getLogger("build")

HERE = Path(__file__).parent
ROOT = HERE.parent
TODAY = date.today()
HORIZON = 5
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def date_phrase(rd, precision):
    """How to describe a retirement date in prose, given what we actually know.

    Our dates come from fan-media reporting and cluster on month-end buckets --
    "end of 2026" reported as 2026-12-31. Rendering that as a precise day, with
    a day countdown, claims knowledge we do not have and that a knowledgeable
    buyer will see through. So a period-precision date is described as a period.

    Returns (long phrase, short label, url slug).
    """
    if precision == "exact":
        return (f"{rd.day} {MONTHS[rd.month]} {rd.year}",
                f"{rd.day} {MONTHS[rd.month][:3]} {rd.year}",
                f"{MONTHS[rd.month].lower()}-{rd.year}")
    if rd.month == 12:
        return f"the end of {rd.year}", f"End {rd.year}", f"end-{rd.year}"
    if rd.month <= 4:
        return f"early {rd.year}", f"Early {rd.year}", f"early-{rd.year}"
    if rd.month <= 8:
        return f"mid-{rd.year}", f"Mid {rd.year}", f"mid-{rd.year}"
    return f"late {rd.year}", f"Late {rd.year}", f"late-{rd.year}"


# --------------------------------------------------------------------------
# data prep
# --------------------------------------------------------------------------

def enrich(sets, prices, mkt):
    """Attach model output and price-derived fields to every set, for one market.

    Returns a fresh list -- the same set dict must not carry one market's
    numbers into another market's build.
    """
    code = mkt["code"]
    out = []
    for src in sets:
        s = dict(src)
        rrp = s["rrp"].get(code)
        if rrp is None:
            # No RRP for this market means we cannot model or price it here.
            continue
        s["rrp"] = rrp
        rd = date.fromisoformat(s["retirement_date"])
        g, parts = G.growth_rate(s["theme"], rrp, s["flags"], mkt)
        s["growth"] = g
        s["growth_parts"] = parts
        s["confidence"] = G.confidence(s["theme"], s["flags"])
        s["ship"] = G.shipping_cost(rrp, mkt)
        s["retire"] = rd
        s["days_out"] = (rd - TODAY).days
        s["precision"] = s.get("date_precision", "period")
        long_p, short_p, slug = date_phrase(rd, s["precision"])
        s["wave_slug"] = slug
        s["retire_label"] = short_p
        s["retire_label_long"] = long_p
        s["is_estimate"] = s["precision"] != "exact"
        p = prices.get(s["set_number"])
        if p:
            best = p["best"]["price"]
            p["saving_pct"] = (rrp - best) / rrp * 100
        out.append(s)
    return out


def projection_rows(s, buy, mkt, years_list=(2, 3, 5, 7, 10)):
    rows = []
    for y in years_list:
        at = date(TODAY.year + y, TODAY.month, min(TODAY.day, 28))
        gross = G.projected_value(s["rrp"], s["growth"], s["retire"], at)
        net = G.net_proceeds(gross, s["rrp"], mkt)
        rows.append({"years": y, "gross": gross, "net": net,
                     "cagr": G.cagr(net, buy, y), "highlight": y == HORIZON})
    return rows


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

class Site:
    """Renders pages for one market at a time, under that market's prefix.

    Every content URL is `/<market>/...`. Nothing is served from the root
    except a redirect stub, so adding a market never moves an existing URL.
    """

    def __init__(self, out: Path):
        self.out = out
        self.env = Environment(
            loader=FileSystemLoader(HERE / "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True, lstrip_blocks=True,
        )
        self.urls: list[str] = []
        self.mkt: dict | None = None

    def for_market(self, mkt: dict) -> "Site":
        self.mkt = mkt
        return self

    def render(self, path: str, template: str, **ctx):
        """`path` is market-relative, e.g. 'retiring/2026/'.

        Written to /<market>/<path>/index.html.
        """
        code = self.mkt["code"]
        full = f"{code}/{path}" if path else f"{code}/"
        # Two different "up" paths, and mixing them up silently produces links
        # that 404 only in the market subfolder:
        #   rel      -> this market's root, for every content link
        #   root_rel -> the site root, for /static/ which is shared
        depth_in_market = len([p for p in path.split("/") if p])
        ctx.setdefault("rel", "../" * depth_in_market)
        ctx.setdefault("root_rel", "../" * (depth_in_market + 1))
        ctx.setdefault("canonical", "/" + full)
        ctx.setdefault("market", self.mkt)
        # hreflang alternates: every enabled market's equivalent page, plus an
        # x-default so searchers who match no market get the default one rather
        # than whichever Google guesses.
        ctx.setdefault("alternates", [
            {"hreflang": m["hreflang"],
             "href": f"{config.BASE_URL}/{m['code']}/{path}"}
            for m in config.enabled_markets()
        ] + [
            {"hreflang": "x-default",
             "href": f"{config.BASE_URL}/{config.DEFAULT_MARKET}/{path}"}
        ])
        ctx.setdefault("brand", config.BRAND)
        ctx.setdefault("tagline", config.TAGLINE)
        ctx.setdefault("base_url", config.BASE_URL)
        ctx.setdefault("noindex", config.NOINDEX)
        ctx.setdefault("affiliate_active", config.AFFILIATE_ACTIVE)
        ctx.setdefault("build_date", TODAY.isoformat())
        html = self.env.get_template(template).render(**ctx)
        dest = self.out / full / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        self.urls.append("/" + full)

    def root_redirect(self):
        """Static root stub pointing at the default market.

        GitHub Pages cannot issue a 301, so this is a noindex meta-refresh
        rather than a real redirect. It is deliberately not in the sitemap:
        the canonical entry point for crawlers is /<default market>/.
        """
        d = config.DEFAULT_MARKET
        html = f"""<!doctype html>
<html lang="{config.market(d)['locale']}">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url=/{d}/">
<link rel="canonical" href="{config.BASE_URL}/{d}/">
<title>{config.BRAND}</title>
</head>
<body><p>Redirecting to <a href="/{d}/">{config.BRAND}</a>.</p></body>
</html>
"""
        (self.out / "index.html").write_text(html, encoding="utf-8")

    def cname(self):
        """GitHub Pages custom-domain marker.

        With an Actions-based deploy the published artifact is the whole site,
        so the CNAME has to be generated into it -- otherwise the custom domain
        can be dropped on the next deploy. Harmless before the domain is live.
        """
        if config.DOMAIN and "." in config.DOMAIN:
            (self.out / "CNAME").write_text(config.DOMAIN + "\n")

    def sitemap(self):
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for u in sorted(set(self.urls)):
            lines.append(f"  <url><loc>{config.BASE_URL}{u}</loc>"
                         f"<lastmod>{TODAY.isoformat()}</lastmod></url>")
        lines.append("</urlset>")
        (self.out / "sitemap.xml").write_text("\n".join(lines))
        robots = ("User-agent: *\nDisallow: /\n" if config.NOINDEX else
                  f"User-agent: *\nAllow: /\nSitemap: {config.BASE_URL}/sitemap.xml\n")
        (self.out / "robots.txt").write_text(robots)

def build_market(site, all_sets, mkt):
    """Render every page for one market. Returns the number of pages written."""
    code = mkt["code"]
    adj = mkt["adjective"]
    money = lambda v, dp=2: config.money(v, mkt, dp)
    prices = normalise.load_current(ROOT / config.DATA_DIR, code)
    sets = enrich(all_sets, prices, mkt)
    if not sets:
        log.warning("market %s: no sets have an RRP for this market — skipping", code)
        return 0

    site.for_market(mkt)
    before = len(site.urls)

    priced = lambda ss: sum(1 for s in ss if s["set_number"] in prices)
    best_saving = lambda ss: max((prices[s["set_number"]]["saving_pct"]
                                  for s in ss if s["set_number"] in prices), default=0)

    by_wave, by_year, by_theme = defaultdict(list), defaultdict(list), defaultdict(list)
    for s in sets:
        by_wave[s["wave_slug"]].append(s)
        by_year[s["retire"].year].append(s)
        by_theme[s["theme_slug"]].append(s)

    common = dict(prices=prices, price_updated=TODAY.strftime("%-d %B %Y"))

    def item_list(ss):
        return [{"@type": "ListItem", "position": i + 1, "name": s["name"],
                 "url": f"{config.BASE_URL}/{code}/sets/{s['slug']}/"}
                for i, s in enumerate(ss[:50])]

    def listing(path, ss, *, h1, lede, eyebrow, days_out=None, show_theme=True,
                related=None, body_html=None, title=None, desc=None):
        site.render(path, "listing.html", sets=ss, h1=h1, lede=lede,
                    eyebrow=eyebrow, days_out=days_out, show_theme=show_theme,
                    priced_count=priced(ss), best_saving=best_saving(ss),
                    related=related or [], body_html=body_html,
                    item_list=item_list(ss),
                    page_title=title or f"{h1} | {config.BRAND}",
                    meta_description=desc or lede[:158], **common)

    # ---- hub ------------------------------------------------------------
    waves = [{"slug": w, "label": ss[0]["retire_label_long"], "count": len(ss),
              "days_out": ss[0]["days_out"]}
             for w, ss in sorted(by_wave.items(), key=lambda kv: kv[1][0]["retire"])]
    themes = sorted(({"slug": t, "name": ss[0]["theme"], "count": len(ss)}
                     for t, ss in by_theme.items()), key=lambda t: -t["count"])

    site.render("retiring/", "hub.html",
        eyebrow=f"{adj} · updated daily", h1="LEGO sets retiring soon",
        lede=f"Every LEGO set due to leave shelves in the next twelve months — "
             f"{len(sets)} of them — with {adj} prices and the date each one goes.",
        total=len(sets), waves=waves, themes=themes, priced_count=priced(sets),
        page_title=f"LEGO Sets Retiring Soon — {adj} list, updated daily | {config.BRAND}",
        meta_description=f"All {len(sets)} LEGO sets retiring in the next 12 months, "
                         f"with {adj} prices, retirement dates and the best deals before they go.",
        **common)
    # ---- home ------------------------------------------------------------
    # Deliberately NOT the same content as /retiring/. The retiring hub is the
    # full index; home is the front door -- nearest deadline first, then the
    # calendar, then what the site is for. Rendering hub.html at both URLs
    # previously produced ~79% duplicate text between them.
    now_next = waves[0] if waves else None
    featured = []
    if now_next:
        in_wave = by_wave[now_next["slug"]]
        # the ones people recognise: exclusives and icons first, then biggest
        featured = sorted(in_wave,
                          key=lambda s: (-int("d2c" in s["flags"] or "icon" in s["flags"]),
                                         -s["rrp"]))[:4]
    home_schema = {
        "@context": "https://schema.org", "@type": "WebSite",
        "name": config.BRAND, "url": f"{config.BASE_URL}/{code}/",
        "description": (f"Every LEGO set retiring in the next twelve months, with "
                        f"{adj} prices and retirement dates."),
    }
    site.render("", "home.html",
        total=len(sets), waves=waves, themes=themes, priced_count=priced(sets),
        next_wave=now_next, featured=featured, home_schema=home_schema,
        page_title=f"{config.BRAND} — {adj} {config.TAGLINE}",
        meta_description=(f"{len(sets)} LEGO sets are retiring in the next twelve "
                          f"months. See what goes when, and what it costs in the "
                          f"{adj} before it does."),
        **common)

    # ---- waves ----------------------------------------------------------
    for slug, ss in by_wave.items():
        w = ss[0]
        period = w["retire_label_long"]
        listing(f"retiring/{slug}/", ss,
            eyebrow=f"Expected to retire {period}",
            h1=f"LEGO sets retiring {period}",
            lede=f"{len(ss)} sets are expected to leave shelves around "
                 f"{period}. Dates are reported by fan media rather than announced "
                 f"by LEGO, so treat them as a window, not a deadline.",
            days_out=None,
            title=f"LEGO Sets Retiring {period.title()} — full {adj} list | {config.BRAND}",
            desc=f"The {len(ss)} LEGO sets expected to retire around {period}, "
                 f"with {adj} prices and RRP.",
            related=[{"href": f"../{o['slug']}/", "label": f"Retiring {o['label']}"}
                     for o in waves if o["slug"] != slug])

    # ---- years ----------------------------------------------------------
    for year, ss in by_year.items():
        listing(f"retiring/{year}/", ss,
            eyebrow=f"{len(ss)} sets · {len({s['wave_slug'] for s in ss})} waves",
            h1=f"LEGO sets retiring in {year}",
            lede=f"Every LEGO set retiring during {year}, grouped by the date it leaves "
                 f"shelves, with current {adj} prices.",
            title=f"LEGO Sets Retiring {year} — complete {adj} list | {config.BRAND}",
            desc=f"All {len(ss)} LEGO sets retiring in {year}, with {adj} prices, "
                 "retirement dates and the biggest current savings.",
            related=[{"href": f"../{y}/", "label": f"Sets retiring in {y}"}
                     for y in sorted(by_year) if y != year])

    # ---- themes ---------------------------------------------------------
    for slug, ss in by_theme.items():
        theme = ss[0]["theme"]
        listing(f"retiring/{slug}/", ss, show_theme=False,
            eyebrow=f"{theme} · retiring",
            h1=f"LEGO {theme} sets retiring soon",
            lede=f"{len(ss)} LEGO {theme} sets are retiring within the next twelve "
                 f"months. Cheapest current {adj} price shown for each.",
            title=f"LEGO {theme} Sets Retiring Soon — {adj} prices | {config.BRAND}",
            desc=f"{len(ss)} LEGO {theme} sets retiring soon, with {adj} prices and dates.",
            related=[{"href": f"../{t['slug']}/", "label": f"{t['name']} retiring soon"}
                     for t in themes[:8] if t["slug"] != slug])

    # ---- tracker --------------------------------------------------------
    listing("tracker/", sorted(sets, key=lambda s: -(prices.get(s["set_number"], {}).get("saving_pct") or 0)),
        eyebrow="All sets · sorted by current saving",
        h1="The full retirement tracker",
        lede=f"All {len(sets)} retiring sets in one table, ordered by how far below "
             f"RRP we can currently find them in the {adj}.",
        title=f"LEGO Retirement Tracker — all {len(sets)} sets | {config.BRAND}",
        desc=f"Every retiring LEGO set with live {adj} prices, sorted by biggest saving.")

    # ---- set pages ------------------------------------------------------
    for s in sets:
        p = prices.get(s["set_number"])
        buy = p["best"]["price"] if p else s["rrp"]
        basis = (f"the best price we found ({money(buy)})" if p
                 else f"RRP ({money(s['rrp'])})")
        siblings = [o for o in by_theme[s["theme_slug"]] if o["slug"] != s["slug"]][:5]

        schema = {
            "@context": "https://schema.org", "@type": "Product",
            "name": f"LEGO {s['name']}", "sku": s["set_number"],
            "mpn": s["set_number"], "brand": {"@type": "Brand", "name": "LEGO"},
            "category": s["theme"],
            "url": f"{config.BASE_URL}/{code}/sets/{s['slug']}/",
        }
        if p:
            schema["offers"] = {
                "@type": "AggregateOffer", "priceCurrency": mkt["currency"],
                "lowPrice": round(min(q["price"] for q in p["all"]), 2),
                "highPrice": round(max(q["price"] for q in p["all"]), 2),
                "offerCount": len(p["all"]),
                "availability": ("https://schema.org/InStock" if p["any_in_stock"]
                                 else "https://schema.org/OutOfStock"),
            }

        retire_prose = (
            f"{s['name']} is expected to be discontinued around "
            f"{s['retire_label_long']}. That is reported by fan media, not announced "
            f"by LEGO, so it is a window rather than a date — sets get extended, "
            f"pulled early and occasionally re-released. Once retail "
            f"stock clears, the only supply is the secondary market. Sets in the "
            f"{s['theme']} theme have historically appreciated at around "
            f"{s['growth'] * 100:.0f}% a year once sealed stock dries up, though "
            f"individual sets vary enormously and our confidence for this one is "
            f"{s['confidence']}."
        )

        site.render(f"sets/{s['slug']}/", "set.html", s=s, price=p,
            lede=(f"{adj} RRP {money(s['rrp'])}. Expected to retire around "
                  f"{s['retire_label_long']}."),
            days_out=s["days_out"], projection=projection_rows(s, buy, mkt),
            buy_basis=basis, fee=G.selling_fee(mkt), siblings=siblings,
            wave_slug=s["wave_slug"], product_schema=schema,
            retire_prose=retire_prose,
            page_title=f"LEGO {s['name']} {s['set_number']} — {adj} price & retirement | {config.BRAND}",
            meta_description=(f"LEGO {s['name']} ({s['set_number']}) is expected to "
                              f"retire around {s['retire_label_long']}. {adj} RRP "
                              f"{money(s['rrp'])}. Compare prices before it goes."),
            **common)

    # ---- trust pages -----------------------------------------------------
    # Networks judge the site before approving it, and UK GDPR wants a named
    # controller. These three pages are not optional decoration.
    owner_ready = not (config.OWNER_NAME.startswith("TODO")
                       or config.CONTACT_EMAIL.startswith("TODO"))
    if not owner_ready:
        log.warning("config.OWNER_NAME / CONTACT_EMAIL still TODO — "
                    "about/privacy/contact NOT rendered")
    else:
        owner, email = config.OWNER_NAME, config.CONTACT_EMAIL

        site.render("about/", "page.html",
            eyebrow="About",
            h1=f"About {config.BRAND}",
            lede=f"A one-person site tracking which LEGO sets are leaving shelves, "
                 f"run from the {adj}.",
            body_html=f"""
<h2>What this is</h2>
<p>{config.BRAND} lists every LEGO set expected to retire in the next twelve months —
{len(sets)} of them right now — with the {adj} price where we have one, and a model of
what holding a set sealed might be worth once it is gone.</p>
<h2>Who runs it</h2>
<p>It is built and maintained by {owner}, a LEGO collector in the {adj}, working as a
{config.BUSINESS_TYPE}. There is no company behind it and no team. If something here is
wrong, <a href="../contact/">tell me</a> and I will fix it.</p>
<h2>Where the information comes from</h2>
<p>Retirement timing is compiled from fan media — chiefly Brick Fanatics — which reports
LEGO's expected end-of-production windows. <b>LEGO does not publish a retirement
calendar</b>, so every date here is an estimate with a margin of error, and we say so on
every page rather than dressing a guess up as a deadline. Sets get extended, pulled early
and occasionally re-released.</p>
<p>Prices are collected from {adj} retailers and refreshed daily. RRP is LEGO's own
recommended price. The value model is documented in full on the
<a href="../method/">method page</a>, including the academic study it is
anchored to and the things it cannot tell you.</p>
<h2>What this is not</h2>
<p>It is not investment advice, and I am not a financial adviser. Sealed LEGO is an
illiquid, unregulated collectables market where individual outcomes vary enormously.
Treat the projections as a way of thinking about a purchase, not a forecast.</p>
<p>{config.BRAND} is not affiliated with, endorsed by, or connected to the LEGO Group.
LEGO&reg; is a trademark of the LEGO Group.</p>
""",
            page_title=f"About {config.BRAND}",
            meta_description=(f"Who runs {config.BRAND}, where the retirement dates and "
                              f"{adj} prices come from, and what the site does not claim."),
            **common)

        disclosure = ("""
<h2>Affiliate links</h2>
<p>Some links to retailers earn a commission if you buy through them, at no extra cost to
you. It does not change which retailer we show: the table is ordered by price, and the
cheapest in-stock option wins whether or not it pays us.</p>
""" if config.AFFILIATE_ACTIVE else """
<h2>Affiliate links</h2>
<p>There are none yet. If that changes, this page will say so before any link earns
anything, and commission will never affect which retailer we show — the table is ordered
by price.</p>
""")

        site.render("privacy/", "page.html",
            eyebrow="Privacy",
            h1="Privacy policy",
            lede="What this site collects, which is almost nothing.",
            body_html=f"""
<h2>The short version</h2>
<p>This is a static website. There are no accounts, no logins, no forms, no newsletter,
no advertising network, and <b>no cookies set by us</b>. We do not run analytics, so we
cannot see who you are or what you looked at.</p>
<h2>What is unavoidably processed</h2>
<p>The site is hosted on GitHub Pages. Like any web host, GitHub receives your IP address
and browser user-agent in order to serve the page, and may log it for security and abuse
prevention. That processing is GitHub's, under
<a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement"
rel="nofollow noopener" target="_blank">their privacy statement</a>. We never see it.</p>
<h2>Links to retailers</h2>
<p>When you follow a link to a retailer you leave this site, and that retailer's own
privacy policy and cookies apply. We have no control over and no visibility into what
they collect.</p>
{disclosure}
<h2>Your rights</h2>
<p>Under UK GDPR you have rights of access, correction and erasure over personal data
held about you. Since we hold none, there is nothing to access or erase — but if you
believe otherwise, email {email} and we will look into it. You can also complain to the
Information Commissioner's Office at
<a href="https://ico.org.uk" rel="nofollow noopener" target="_blank">ico.org.uk</a>.</p>
<h2>Changes</h2>
<p>If we add analytics or affiliate tracking, this page is updated before it goes live,
not after. Data controller: {owner}, contactable at {email}.</p>
<p class="small">Last updated {TODAY.strftime('%-d %B %Y')}.</p>
""",
            page_title=f"Privacy policy | {config.BRAND}",
            meta_description=("What this site collects: no cookies, no analytics, no "
                              "accounts. Hosting and outbound links explained."),
            **common)

        site.render("contact/", "page.html",
            eyebrow="Contact",
            h1="Get in touch",
            lede="Corrections especially welcome.",
            body_html=f"""
<h2>Email</h2>
<p><a href="mailto:{email}">{email}</a></p>
<p>Run by {owner} ({config.BUSINESS_TYPE}, {adj}).</p>
<h2>Corrections</h2>
<p>If a retirement window, an RRP or a price is wrong, please say so — include the set
number and what you are seeing. Retirement timing in particular is compiled from fan
media and is the thing most likely to be out of date. Corrections get fixed faster than
anything else in the inbox.</p>
<h2>Retailers and networks</h2>
<p>If you run a {adj} LEGO retailer or an affiliate programme and want to be included,
email the address above. Inclusion is based on price and stock, not on commercial terms.</p>
""",
            page_title=f"Contact | {config.BRAND}",
            meta_description=f"How to contact {config.BRAND} with corrections or "
                             f"retailer enquiries.",
            **common)

    # ---- method ---------------------------------------------------------
    adj_html = "".join(
        f"<li><b>{'+' if v > 0 else ''}{v*100:.1f}pp</b> — {label}</li>"
        for v, label in sorted(G.FLAG_ADJ.values(), reverse=True))
    lo, mid, high, flag = mkt["rrp_bands"]
    site.render("method/", "page.html",
        eyebrow="How the numbers are made",
        h1="How we calculate projected value",
        lede="Every figure on this site comes from a model you can inspect and "
             "disagree with. Here is exactly what it does.",
        body_html=f"""
<h2>The base rate</h2>
<p>Dobrynskaya and Kishilova studied 2,322 retired LEGO sets between 1987 and 2015 and
found roughly <b>11% nominal annual appreciation</b> on sealed sets, with a standard
deviation of 25–28% and about 90% of sets finishing positive. That 11% is our anchor.
Returns were U-shaped in set size — small sets and large flagships beat the crowded
middle — so we adjust by RRP band at both ends. In this market those bands sit at
{money(lo, 0)}, {money(mid, 0)}, {money(high, 0)} and {money(flag, 0)}.</p>
<h2>The adjustments</h2>
<ul>{adj_html}</ul>
<h2>The value path</h2>
<p>A sealed set holds at RRP until it retires, then stays flat for a further
<b>{G.FLAT_MONTHS} months</b> while remaining retail stock clears. Only after that does it
compound at its modelled rate. Your return is calculated from <i>your</i> purchase price,
after a <b>{G.selling_fee(mkt)*100:.0f}% selling fee</b> and estimated postage — not from RRP.
Buying 30% below RRP is worth more than any theme premium in our table.</p>
<h2>What this model cannot do</h2>
<p>It is a smoothed average applied to individual sets, and individual sets are wildly
dispersed — the same study found single-set outcomes ranging from −54% to +613% a year.
Sealed condition, storage and honest grading do most of the work in a real sale, and none
of that is modelled. Retirement dates are LEGO's reported intentions compiled from fan
media, not commitments: sets get extended, pulled early, and re-released.</p>
<p>This is a research tool. It is not investment advice, and we are not financial advisers.</p>
""",
        page_title=f"How we calculate LEGO set values | {config.BRAND}",
        meta_description="The model behind our projections: base rates, theme "
                         "adjustments, fees, and what it cannot tell you.",
        **common)

    written = len(site.urls) - before
    log.info("market %-3s: %d sets, %d priced, %d pages",
             code, len(sets), priced(sets), written)
    return written


def build():
    all_sets = json.loads((ROOT / config.DATA_DIR / "sets.json").read_text())

    out = ROOT / config.OUT_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(HERE / "static", out / "static")

    site = Site(out)
    markets = config.enabled_markets()
    if not markets:
        raise SystemExit("no enabled markets in config.MARKETS")

    for mkt in markets:
        build_market(site, all_sets, mkt)

    site.root_redirect()
    site.cname()
    site.sitemap()
    log.info("built %d pages across %d market(s) into %s",
             len(site.urls), len(markets), out)
    return len(site.urls)


if __name__ == "__main__":
    build()
