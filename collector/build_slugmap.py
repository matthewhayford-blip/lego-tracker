#!/usr/bin/env python3
"""Build a set_number -> bricktracker slug map by crawling theme pages.

Why this exists: bricktracker product URLs are /lego-sets/<slug>-<number>,
and there is no sitemap or number-only URL that resolves. A wrong slug does
NOT 404 -- it silently serves the homepage -- so guessing is dangerous. The
only safe route is to read the slugs the site itself publishes.

Writes data/bricktracker_slugs.json:
    {"generated_at": ..., "slugs": {"75192": "lego-star-wars-millennium-falcon-75192", ...}}

Also reports how many of our tracked sets were found, which is the number
that decides whether this source is worth keeping at all.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.sources.base import HttpSource, SourceError

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("slugmap")

BASE = "https://www.bricktracker.co.uk"
THEMES_URL = f"{BASE}/themes"
THEME_HREF_RE = re.compile(r'href="(/themes/[^"]+)"')
# Slugs end in the set number; capture both so we can key by number.
PRODUCT_HREF_RE = re.compile(r'href="/lego-sets/([^"]*?(\d{4,7}))"')

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "bricktracker_slugs.json"


def theme_paths(html: str) -> list[str]:
    seen, out = set(), []
    for path in THEME_HREF_RE.findall(html):
        if path == "/themes" or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def slugs_from(html: str) -> dict[str, str]:
    found = {}
    for slug, number in PRODUCT_HREF_RE.findall(html):
        # Trust the trailing number in the slug as the set number.
        found.setdefault(number, slug)
    return found


def main() -> int:
    src = HttpSource()
    src.name = "bricktracker-slugmap"

    log.info("fetching theme index")
    index_html = src.get(THEMES_URL)
    paths = theme_paths(index_html)
    log.info("found %d themes", len(paths))
    if not paths:
        raise SourceError("no theme links found on /themes -- structure changed")

    slugs: dict[str, str] = {}
    for i, path in enumerate(paths, 1):
        url = f"{BASE}{path}"
        try:
            html = src.get(url)
        except SourceError as exc:
            log.warning("theme %s failed: %s", path, exc)
            continue
        got = slugs_from(html)
        new = {k: v for k, v in got.items() if k not in slugs}
        slugs.update(new)
        log.info("[%d/%d] %s -> %d products (%d new, %d total)",
                 i, len(paths), path, len(got), len(new), len(slugs))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "bricktracker theme crawl",
        "slugs": dict(sorted(slugs.items())),
    }, indent=2), encoding="utf-8")

    # -- the number that actually matters ------------------------------
    tracked = [s["set_number"] for s in
               json.loads((ROOT / "data" / "sets.json").read_text())]
    hits = [n for n in tracked if n in slugs]
    log.info("=" * 60)
    log.info("bricktracker slugs discovered : %d", len(slugs))
    log.info("our tracked sets              : %d", len(tracked))
    log.info("COVERAGE of tracked sets      : %d (%.1f%%)",
             len(hits), 100 * len(hits) / max(1, len(tracked)))
    log.info("=" * 60)
    if hits[:10]:
        log.info("sample matches: %s", ", ".join(hits[:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
