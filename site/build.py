#!/usr/bin/env python3
"""Turn data/ into a static site of pre-rendered pages.

Every page ships complete HTML: no JavaScript is required to read any content,
because Google has to see the price tables.
"""
from __future__ import annotations

import json
import logging
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

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


# --------------------------------------------------------------------------
# data prep
# --------------------------------------------------------------------------

def enrich(sets, prices):
    """Attach model output and price-derived fields to every set."""
    for s in sets:
        rd = date.fromisoformat(s["retirement_date"])
        g, parts = G.growth_rate(s["theme"], s["rrp_gbp"], s["flags"])
        s["growth"] = g
        s["growth_parts"] = parts
        s["confidence"] = G.confidence(s["theme"], s["flags"])
        s["ship"] = G.shipping_cost(s["rrp_gbp"])
        s["retire"] = rd
        s["days_out"] = (rd - TODAY).days
        s["wave_slug"] = f"{MONTHS[rd.month].lower()}-{rd.year}"
        s["retire_label"] = f"{rd.day} {MONTHS[rd.month][:3]} {rd.year}"
        s["retire_label_long"] = f"{rd.day} {MONTHS[rd.month]} {rd.year}"
        p = prices.get(s["set_number"])
        if p:
            best = p["best"]["price_gbp"]
            p["saving_pct"] = (s["rrp_gbp"] - best) / s["rrp_gbp"] * 100
    return sets


def projection_rows(s, buy, years_list=(2, 3, 5, 7, 10)):
    rows = []
    for y in years_list:
        at = date(TODAY.year + y, TODAY.month, min(TODAY.day, 28))
        gross = G.projected_value(s["rrp_gbp"], s["growth"], s["retire"], at)
        net = G.net_proceeds(gross, s["rrp_gbp"])
        rows.append({"years": y, "gross": gross, "net": net,
                     "cagr": G.cagr(net, buy, y), "highlight": y == HORIZON})
    return rows


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

class Site:
    def __init__(self, out: Path):
        self.out = out
        self.env = Environment(
            loader=FileSystemLoader(HERE / "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True, lstrip_blocks=True,
        )
        self.urls: list[str] = []

    def render(self, path: str, template: str, **ctx):
        """path is a URL path like 'retiring/2026/'. Writes index.html under it."""
        depth = len([p for p in path.split("/") if p])
        ctx.setdefault("rel", "../" * depth)
        ctx.setdefault("canonical", "/" + path)
        ctx.setdefault("brand", config.BRAND)
        ctx.setdefault("tagline", config.TAGLINE)
        ctx.setdefault("base_url", config.BASE_URL)
        ctx.setdefault("noindex", config.NOINDEX)
        ctx.setdefault("affiliate_active", config.AFFILIATE_ACTIVE)
        ctx.setdefault("build_date", TODAY.isoformat())
        html = self.env.get_template(template).render(**ctx)
        dest = self.out / path / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
        self.urls.append("/" + path)

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


def build():
    sets = json.loads((ROOT / config.DATA_DIR / "sets.json").read_text())
    prices = normalise.load_current(ROOT / config.DATA_DIR)
    sets = enrich(sets, prices)

    out = ROOT / config.OUT_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(HERE / "static", out / "static")

    site = Site(out)
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
                 "url": f"{config.BASE_URL}/sets/{s['slug']}/"}
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
        eyebrow="UK · updated daily", h1="LEGO sets retiring soon",
        lede=f"Every LEGO set due to leave shelves in the next twelve months — "
             f"{len(sets)} of them — with UK prices and the date each one goes.",
        total=len(sets), waves=waves, themes=themes, priced_count=priced(sets),
        page_title=f"LEGO Sets Retiring Soon — UK list, updated daily | {config.BRAND}",
        meta_description=f"All {len(sets)} LEGO sets retiring in the next 12 months, "
                         "with UK prices, retirement dates and the best deals before they go.",
        **common)
    site.render("", "hub.html",
        eyebrow="UK LEGO retirement tracker", h1=config.BRAND,
        lede="Which LEGO sets are retiring, when they go, and what they cost right now "
             "across UK retailers.",
        total=len(sets), waves=waves, themes=themes, priced_count=priced(sets),
        page_title=f"{config.BRAND} — {config.TAGLINE}",
        meta_description="Track LEGO sets retiring soon in the UK, with live prices "
                         "and retirement dates.", **common)

    # ---- waves ----------------------------------------------------------
    for slug, ss in by_wave.items():
        w = ss[0]
        month_year = w["retire_label_long"].split(" ", 1)[1]
        listing(f"retiring/{slug}/", ss,
            eyebrow=f"Retirement wave · {w['days_out']} days out",
            h1=f"LEGO sets retiring {month_year}",
            lede=f"{len(ss)} sets are scheduled to retire on {w['retire_label_long']}. "
                 "Prices below are the cheapest we have found in the UK.",
            days_out=w["days_out"],
            title=f"LEGO Sets Retiring {month_year} — full UK list | {config.BRAND}",
            desc=f"The complete list of {len(ss)} LEGO sets retiring {month_year}, "
                 "with UK prices and savings. Updated daily.",
            related=[{"href": f"../{o['slug']}/", "label": f"Retiring {o['label']}"}
                     for o in waves if o["slug"] != slug])

    # ---- years ----------------------------------------------------------
    for year, ss in by_year.items():
        listing(f"retiring/{year}/", ss,
            eyebrow=f"{len(ss)} sets · {len({s['wave_slug'] for s in ss})} waves",
            h1=f"LEGO sets retiring in {year}",
            lede=f"Every LEGO set retiring during {year}, grouped by the date it leaves "
                 "shelves, with current UK prices.",
            title=f"LEGO Sets Retiring {year} — complete UK list | {config.BRAND}",
            desc=f"All {len(ss)} LEGO sets retiring in {year}, with UK prices, "
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
                 "months. Cheapest current UK price shown for each.",
            title=f"LEGO {theme} Sets Retiring Soon — UK prices | {config.BRAND}",
            desc=f"{len(ss)} LEGO {theme} sets retiring soon, with UK prices and dates.",
            related=[{"href": f"../{t['slug']}/", "label": f"{t['name']} retiring soon"}
                     for t in themes[:8] if t["slug"] != slug])

    # ---- tracker --------------------------------------------------------
    listing("tracker/", sorted(sets, key=lambda s: -(prices.get(s["set_number"], {}).get("saving_pct") or 0)),
        eyebrow="All sets · sorted by current saving",
        h1="The full retirement tracker",
        lede=f"All {len(sets)} retiring sets in one table, ordered by how far below "
             "RRP we can currently find them in the UK.",
        title=f"LEGO Retirement Tracker — all {len(sets)} sets | {config.BRAND}",
        desc="Every retiring LEGO set with live UK prices, sorted by biggest saving.")

    # ---- set pages ------------------------------------------------------
    for s in sets:
        p = prices.get(s["set_number"])
        buy = p["best"]["price_gbp"] if p else s["rrp_gbp"]
        basis = (f"the best price we found (£{buy:.2f})" if p
                 else f"RRP (£{s['rrp_gbp']:.2f})")
        siblings = [o for o in by_theme[s["theme_slug"]] if o["slug"] != s["slug"]][:5]

        schema = {
            "@context": "https://schema.org", "@type": "Product",
            "name": f"LEGO {s['name']}", "sku": s["set_number"],
            "mpn": s["set_number"], "brand": {"@type": "Brand", "name": "LEGO"},
            "category": s["theme"],
            "url": f"{config.BASE_URL}/sets/{s['slug']}/",
        }
        if p:
            schema["offers"] = {
                "@type": "AggregateOffer", "priceCurrency": "GBP",
                "lowPrice": round(min(q["price_gbp"] for q in p["all"]), 2),
                "highPrice": round(max(q["price_gbp"] for q in p["all"]), 2),
                "offerCount": len(p["all"]),
                "availability": ("https://schema.org/InStock" if p["any_in_stock"]
                                 else "https://schema.org/OutOfStock"),
            }

        retire_prose = (
            f"LEGO is scheduled to stop producing {s['name']} on "
            f"{s['retire_label_long']} — {s['days_out']} days from now. Once retail "
            f"stock clears, the only supply is the secondary market. Sets in the "
            f"{s['theme']} theme have historically appreciated at around "
            f"{s['growth'] * 100:.0f}% a year once sealed stock dries up, though "
            f"individual sets vary enormously and our confidence for this one is "
            f"{s['confidence']}."
        )

        site.render(f"sets/{s['slug']}/", "set.html", s=s, price=p,
            lede=(f"UK RRP £{s['rrp_gbp']:.2f}. Retiring {s['retire_label_long']}, "
                  f"in {s['days_out']} days."),
            days_out=s["days_out"], projection=projection_rows(s, buy),
            buy_basis=basis, fee=G.SELLING_FEE, siblings=siblings,
            wave_slug=s["wave_slug"], product_schema=schema,
            retire_prose=retire_prose,
            page_title=f"LEGO {s['name']} {s['set_number']} — UK price & retirement date | {config.BRAND}",
            meta_description=(f"LEGO {s['name']} ({s['set_number']}) retires "
                              f"{s['retire_label_long']}. UK RRP £{s['rrp_gbp']:.2f}. "
                              "Compare current UK prices before it goes."),
            **common)

    # ---- method ---------------------------------------------------------
    adj = "".join(
        f"<li><b>{'+' if v > 0 else ''}{v*100:.1f}pp</b> — {label}</li>"
        for v, label in sorted(G.FLAG_ADJ.values(), reverse=True))
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
middle — so we adjust by RRP band at both ends.</p>
<h2>The adjustments</h2>
<ul>{adj}</ul>
<h2>The value path</h2>
<p>A sealed set holds at RRP until it retires, then stays flat for a further
<b>{G.FLAT_MONTHS} months</b> while remaining retail stock clears. Only after that does it
compound at its modelled rate. Your return is calculated from <i>your</i> purchase price,
after a <b>{G.SELLING_FEE*100:.0f}% selling fee</b> and estimated postage — not from RRP.
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

    site.sitemap()
    log.info("built %d pages into %s", len(site.urls), out)
    return len(site.urls)


if __name__ == "__main__":
    build()
