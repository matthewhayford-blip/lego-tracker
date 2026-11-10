#!/usr/bin/env python3
"""Find out which LEGO.com pages we can actually read products from.

Price coverage is currently capped at ~22 sets because `lego_com.py` reads one
page: the retiring-soon category. Everything LEGO sells that is not flagged
retiring is invisible to us.

Before writing a wider collector I want evidence rather than guesses — writing
parsers against assumed URL structure is what produced two dead sources in
September. This tries several patterns and reports, for each, whether it loads
and how many products with prices come out.

Writes data/debug/lego_coverage.json. Run via the debug-fetch workflow; this
sandbox cannot reach lego.com.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.sources.base import (HttpSource, extract_json_ld,  # noqa: E402
                                    offers_from_product)
from collector.sources.lego_com import LegoComSource  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("lego-coverage")

OUT = Path(__file__).resolve().parent.parent / "data" / "debug"
BASE = "https://www.lego.com/en-gb"

# Each is a hypothesis about how LEGO.com exposes its range. We only need the
# ones that work, so breadth matters more than precision here.
CANDIDATES = {
    # known-good control, so a total failure is distinguishable from a bad URL
    "retiring-soon":      f"{BASE}/categories/retiring-soon",
    "last-chance":        f"{BASE}/categories/last-chance-to-buy",
    # whole-range listings
    "shop-all":           f"{BASE}/categories/shop-all",
    "new":                f"{BASE}/categories/new-sets-and-gifts",
    "sale":               f"{BASE}/categories/sales-and-deals",
    # theme pages: the likely route to breadth
    "theme-star-wars":    f"{BASE}/themes/star-wars",
    "theme-technic":      f"{BASE}/themes/technic",
    "theme-icons":        f"{BASE}/themes/icons",
    "theme-city":         f"{BASE}/themes/city",
    # pagination — does the second page work the same way?
    "theme-sw-page2":     f"{BASE}/themes/star-wars?page=2",
    "retiring-page2":     f"{BASE}/categories/retiring-soon?page=2",
}


def products_in(html: str) -> tuple[list[dict], list[dict]]:
    """Try BOTH extraction paths, because they disagree.

    The first version of this probe only tested JSON-LD and reported zero
    products everywhere -- including the page that is demonstrably working in
    production. LEGO.com has evidently dropped or restructured its JSON-LD, and
    the live source succeeds via its HTML fallback. Testing only the path the
    source tries first said nothing useful about what it actually gets.
    """
    jsonld = []
    for node in extract_json_ld(html):
        types = node.get("@type", "")
        types = types if isinstance(types, list) else [types]
        if "Product" not in types:
            continue
        price, in_stock = offers_from_product(node)
        jsonld.append({
            "name": node.get("name"),
            "sku": node.get("sku") or node.get("mpn"),
            "price": str(price) if price is not None else None,
        })

    src = LegoComSource()
    try:
        html_quotes = [{"sku": q.set_number, "price": str(q.price),
                        "in_stock": q.in_stock} for q in src._from_html(html)]
    except Exception as exc:  # noqa: BLE001
        html_quotes = [{"error": str(exc)[:200]}]
    return jsonld, html_quotes


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results, all_skus = {}, set()

    for label, url in CANDIDATES.items():
        src = HttpSource()
        src.name = f"lego-coverage-{label}"
        try:
            html = src.get(url)
        except Exception as exc:  # noqa: BLE001
            results[label] = {"url": url, "error": str(exc)[:300]}
            log.warning("%-18s FAILED", label)
            time.sleep(1.5)
            continue

        jsonld, html_quotes = products_in(html)
        priced = [q for q in html_quotes if q.get("price")]
        skus = {q["sku"] for q in priced if q.get("sku")}
        all_skus |= skus
        results[label] = {
            "url": url,
            "html_bytes": len(html),
            "json_ld_products": len(jsonld),
            "html_products": len(html_quotes),
            "with_price": len(priced),
            "distinct_skus": len(skus),
            "sample": priced[:4],
        }
        log.info("%-18s json-ld %3d | html %4d priced, %4d distinct",
                 label, len(jsonld), len(priced), len(skus))
        time.sleep(1.5)

    results["_summary"] = {
        "distinct_skus_across_all_pages": len(all_skus),
        "working_pages": sorted(k for k, v in results.items()
                                if isinstance(v, dict) and v.get("with_price")),
        "note": ("with_price counts come from the HTML fallback, which is the "
                 "path the live source actually succeeds on. JSON-LD appears "
                 "to have been removed from these pages."),
    }
    (OUT / "lego_coverage.json").write_text(json.dumps(results, indent=1))

    log.info("=" * 60)
    log.info("distinct priced SKUs across all pages: %d", len(all_skus))
    log.info("pages that worked: %s", results["_summary"]["working_pages"])
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
