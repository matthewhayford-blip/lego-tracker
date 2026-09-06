#!/usr/bin/env python3
"""One-off diagnostic: capture real pages from each source into data/debug/.

Not part of the normal collection pipeline. Exists because the environment
this was written in cannot reach lego.com or bricktracker.co.uk directly, but
GitHub Actions runners can. Run this via the debug-fetch workflow, then read
the committed output through raw.githubusercontent.com.

Writes, for each source:
  - the raw HTML of one real page
  - a summary.json noting how many JSON-LD blocks were found, their @type
    values, and (for the first Product node, if any) its top-level keys and
    its 'offers' shape -- enough to see why offers_from_product() is or isn't
    matching, without downloading the full HTML every time.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.sources.base import HttpSource, extract_json_ld, offers_from_product
from collector.sources.lego_com import RETIRING_URL
from collector.sources.bricktracker import SET_URL

OUT = Path(__file__).resolve().parent.parent / "data" / "debug"


def summarise_json_ld(html: str) -> dict:
    nodes = extract_json_ld(html)
    types = []
    first_product = None
    for n in nodes:
        t = n.get("@type", "")
        types.append(t if isinstance(t, str) else list(t) if isinstance(t, list) else str(t))
        if first_product is None:
            tt = t if isinstance(t, list) else [t]
            if "Product" in tt:
                price, in_stock = offers_from_product(n)
                first_product = {
                    "keys": sorted(n.keys()),
                    "offers_raw": n.get("offers"),
                    "parsed_price": str(price) if price is not None else None,
                    "parsed_in_stock": in_stock,
                }
    return {
        "json_ld_block_count": len(nodes),
        "types_seen": types[:20],
        "first_product_node": first_product,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}

    # --- lego.com -----------------------------------------------------
    # First with our own honest bot UA (what the real source uses), then
    # with a plain browser UA, to see whether the 403 is UA-based bot
    # detection or something else (geo-block, WAF rule on the path, etc).
    try:
        src = HttpSource()
        src.name = "lego.com-debug"
        html = src.get(RETIRING_URL)
        (OUT / "lego_com_category.html").write_text(html, encoding="utf-8")
        summary["lego_com_bot_ua"] = {
            "url": RETIRING_URL,
            "html_bytes": len(html),
            **summarise_json_ld(html),
        }
    except Exception as exc:  # noqa: BLE001
        summary["lego_com_bot_ua"] = {"url": RETIRING_URL, "error": str(exc)}

    try:
        src = HttpSource()
        src.name = "lego.com-debug-browser-ua"
        src.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        html = src.get(RETIRING_URL)
        (OUT / "lego_com_category_browserua.html").write_text(html, encoding="utf-8")
        summary["lego_com_browser_ua"] = {
            "url": RETIRING_URL,
            "html_bytes": len(html),
            **summarise_json_ld(html),
        }
    except Exception as exc:  # noqa: BLE001
        summary["lego_com_browser_ua"] = {"url": RETIRING_URL, "error": str(exc)}

    # --- bricktracker.co.uk --------------------------------------------
    # The old /set/{number} pattern 404s. The 404 page itself reveals the
    # real pattern: /lego-sets/<slug>-<number>. Testing a few hypotheses for
    # how to resolve set-number -> slug without already knowing the slug.
    test_set = "75192"  # Millennium Falcon (UCS) -- known real, popular set
    candidates = {
        "number_only": f"https://www.bricktracker.co.uk/lego-sets/{test_set}",
        "placeholder_slug": f"https://www.bricktracker.co.uk/lego-sets/x-{test_set}",
        "search": f"https://www.bricktracker.co.uk/search?q={test_set}",
        "old_pattern": SET_URL.format(set_number=test_set),
    }
    bt_results = {}
    for label, url in candidates.items():
        try:
            src = HttpSource()
            src.name = f"bricktracker-debug-{label}"
            html = src.get(url)
            fname = f"bricktracker_{label}_{test_set}.html"
            (OUT / fname).write_text(html, encoding="utf-8")
            bt_results[label] = {
                "url": url,
                "html_bytes": len(html),
                "is_404_page": "lost a brick" in html,
                **summarise_json_ld(html),
            }
        except Exception as exc:  # noqa: BLE001
            bt_results[label] = {"url": url, "error": str(exc)}
    summary["bricktracker"] = bt_results

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
