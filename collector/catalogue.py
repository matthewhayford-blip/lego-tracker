#!/usr/bin/env python3
"""Import the full LEGO catalogue from Rebrickable's bulk CSVs.

Phase 0 of the rebuild: take the project from 343 hand-compiled sets to the
whole catalogue, so that every other dataset -- prices, retirement estimates,
retired-set performance -- has something to key off.

Rebrickable publishes keyless, daily-regenerated gzipped CSVs. We need two:

    sets.csv.gz    set_num, name, year, theme_id, num_parts, img_url
    themes.csv.gz  id, name, parent_id

Deliberately NOT in scope here:
  * prices -- a catalogue is not a price list
  * retirement dates -- estimated separately, from the `year` this import gives us
  * RRP -- Rebrickable does not carry it; Brickset does, and that is a later job

`set_num` is Rebrickable's form ("75192-1"). The site keys on the bare set
number, so both are kept: `set_number` for joining to existing data, `rb_num`
for going back to Rebrickable.

Run via the catalogue workflow -- the originating sandbox cannot reach
Rebrickable's CDN, but an Actions runner can.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("catalogue")

BASE = "https://cdn.rebrickable.com/media/downloads"
SETS_URL = f"{BASE}/sets.csv.gz"
THEMES_URL = f"{BASE}/themes.csv.gz"

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "catalogue.json"

UA = "RetiredAndRareBot/0.1 (+https://retiredandrare.com; catalogue import)"

# Rebrickable includes a lot that is not a retail boxed set. These are not
# "sets" for our purposes and would wreck every count and average.
MIN_PARTS = 2
MIN_YEAR = 1990


def fetch_csv(url: str) -> list[dict]:
    log.info("fetching %s", url)
    r = requests.get(url, timeout=60, headers={"User-Agent": UA})
    r.raise_for_status()
    text = gzip.decompress(r.content).decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    log.info("  %d rows", len(rows))
    return rows


# NFKD expands these to letters -- "™" becomes "TM", "®" becomes "R" -- which
# would weld "tm" onto the slug of every trademarked set name. LEGO names are
# full of them, so they have to go before normalisation, not after.
TRADEMARKS = str.maketrans("", "", "\u2122\u00ae\u00a9")


def slugify(text: str) -> str:
    text = text.translate(TRADEMARKS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text) or "set"


def theme_lookup(themes: list[dict]) -> dict:
    """Map theme_id -> (display name, root theme name).

    Rebrickable themes nest several levels deep ("Star Wars > Episode IV-VI").
    The site groups by the root, because that is how people search; the leaf is
    kept for display.
    """
    by_id = {t["id"]: t for t in themes}

    def root_of(tid: str, depth: int = 0) -> str:
        t = by_id.get(tid)
        if not t:
            return "Unknown"
        parent = t.get("parent_id") or ""
        if not parent or depth > 10:   # depth guard: data has had cycles before
            return t["name"]
        return root_of(parent, depth + 1)

    return {t["id"]: (t["name"], root_of(t["id"])) for t in themes}


def build() -> dict:
    sets_rows = fetch_csv(SETS_URL)
    themes_rows = fetch_csv(THEMES_URL)
    themes = theme_lookup(themes_rows)

    out, skipped = [], {"parts": 0, "year": 0, "theme": 0}
    for r in sets_rows:
        try:
            parts = int(r.get("num_parts") or 0)
            year = int(r.get("year") or 0)
        except ValueError:
            continue
        if parts < MIN_PARTS:
            skipped["parts"] += 1
            continue
        if year < MIN_YEAR:
            skipped["year"] += 1
            continue
        tname, troot = themes.get(r.get("theme_id", ""), ("Unknown", "Unknown"))
        if troot == "Unknown":
            skipped["theme"] += 1

        rb_num = r["set_num"]
        set_number = rb_num.split("-")[0]
        out.append({
            "set_number": set_number,
            "rb_num": rb_num,
            "name": r["name"],
            "slug": f"{set_number}-{slugify(r['name'])}"[:90],
            "year": year,
            "theme": troot,
            "theme_slug": slugify(troot),
            "theme_detail": tname,
            "num_parts": parts,
            "img_url": r.get("img_url") or None,
        })

    out.sort(key=lambda s: (-s["year"], s["set_number"]))
    log.info("kept %d sets; skipped %s", len(out), skipped)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "rebrickable bulk csv",
        "set_count": len(out),
        "sets": out,
    }


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    size_mb = OUT.stat().st_size / 1_000_000

    years = [s["year"] for s in payload["sets"]]
    themes = {}
    for s in payload["sets"]:
        themes[s["theme"]] = themes.get(s["theme"], 0) + 1
    top = sorted(themes.items(), key=lambda kv: -kv[1])[:10]

    log.info("=" * 60)
    log.info("wrote %s (%.1f MB)", OUT.relative_to(ROOT), size_mb)
    log.info("sets: %d   years: %d-%d   themes: %d",
             payload["set_count"], min(years), max(years), len(themes))
    log.info("largest themes: %s", ", ".join(f"{n} ({c})" for n, c in top))

    # How much of what we already track is present, which is the join that
    # matters -- a low number here means the key format is wrong.
    tracked = json.loads((ROOT / "data" / "sets.json").read_text())
    have = {s["set_number"] for s in payload["sets"]}
    matched = [s for s in tracked if s["set_number"] in have]
    log.info("tracked sets found in catalogue: %d/%d", len(matched), len(tracked))
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
