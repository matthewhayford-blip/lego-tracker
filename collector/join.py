#!/usr/bin/env python3
"""Merge catalogue, Brickset and tracked-set data into one record per set.

Three sources, three different strengths:

    catalogue.json  Rebrickable -- complete coverage, piece counts, themes
    brickset.json   Brickset    -- UK RRP, real UK availability dates, barcodes
    sets.json       hand-built  -- our 343 curated sets, flags, fan-media dates

Precedence is by reliability, not by convenience. A UK date from LEGO's own
store beats a fan-media estimate every time, so where Brickset has
`uk_last_available` it wins and the fan-media date becomes a footnote.

Filtering is marked, not applied. Brickset's `category` separates retail boxed
sets ("Normal") from Gear, Books and Collections, which are catalogue entries
but not things anyone tracks for retirement. This writes `is_retail` and leaves
the decision downstream -- deleting rows here would hide the barcode table from
the scanner, which legitimately wants Gear too.

Output: data/sets_full.json
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("join")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "sets_full.json"

# Brickset categories that represent a retail boxed set someone might track.
RETAIL_CATEGORIES = {"Normal", "Extended"}


def months_between(a: str | None, b: str | None) -> float | None:
    if not (a and b):
        return None
    try:
        d1, d2 = date.fromisoformat(a), date.fromisoformat(b)
    except ValueError:
        return None
    m = (d2 - d1).days / 30.44
    return round(m, 1) if m > 0 else None


def load(name: str, key: str | None = None):
    p = DATA / name
    if not p.exists():
        log.warning("%s not present", name)
        return {} if key else []
    raw = json.loads(p.read_text())
    rows = raw[key] if key else raw
    return rows


def build() -> dict:
    catalogue = load("catalogue.json", "sets")
    brickset = load("brickset.json", "sets")
    tracked = load("sets.json")

    cat_by = {s["set_number"]: s for s in catalogue}
    bs_by = {s["set_number"]: s for s in brickset}
    tr_by = {s["set_number"]: s for s in tracked}

    numbers = sorted(set(cat_by) | set(bs_by) | set(tr_by))
    log.info("merging %d distinct set numbers (catalogue %d, brickset %d, tracked %d)",
             len(numbers), len(cat_by), len(bs_by), len(tr_by))

    out = []
    for n in numbers:
        c, b, t = cat_by.get(n, {}), bs_by.get(n, {}), tr_by.get(n, {})

        first = b.get("uk_first_available")
        last = b.get("uk_last_available")

        # Retirement date, best source first. Brickset's UK date is LEGO's own
        # store record; the fan-media date is a reported estimate.
        if last:
            retire_date, retire_src, precision = last, "brickset-uk", "exact"
        elif t.get("retirement_date"):
            retire_date = t["retirement_date"]
            retire_src = t.get("retirement_source", "fan-media")
            precision = t.get("date_precision", "period")
        else:
            retire_date, retire_src, precision = None, None, None

        category = b.get("category")
        rec = {
            "set_number": n,
            "name": b.get("name") or c.get("name") or t.get("name"),
            "slug": c.get("slug") or t.get("slug"),
            "year": b.get("year") or c.get("year"),
            "theme": c.get("theme") or b.get("theme"),
            "theme_slug": c.get("theme_slug") or t.get("theme_slug"),
            "theme_detail": b.get("subtheme") or c.get("theme_detail"),
            "theme_group": b.get("theme_group"),
            "category": category,
            "is_retail": category in RETAIL_CATEGORIES if category else None,
            "pieces": b.get("pieces") or c.get("num_parts"),
            "minifigs": b.get("minifigs"),
            # --- money ---
            "rrp": {"uk": b.get("rrp_gbp")} if b.get("rrp_gbp")
                   else (t.get("rrp") or {}),
            # --- availability ---
            "uk_first_available": first,
            "uk_last_available": last,
            "observed_lifespan_months": months_between(first, last),
            "retirement_date": retire_date,
            "retirement_source": retire_src,
            "date_precision": precision,
            "retired": bool(last),
            # live = LEGO.com UK sold it and has not stopped
            "live": bool(first and not last),
            # --- scanner ---
            "ean": b.get("ean"),
            "upc": b.get("upc"),
            # --- provenance ---
            "brickset_id": b.get("brickset_id"),
            "flags": t.get("flags") or [],
            "tracked": n in tr_by,
            "sources": [s for s, present in
                        (("catalogue", bool(c)), ("brickset", bool(b)),
                         ("tracked", bool(t))) if present],
        }
        out.append(rec)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "set_count": len(out),
        "sets": out,
    }


def main() -> int:
    payload = build()
    sets = payload["sets"]
    OUT.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

    retail = [s for s in sets if s["is_retail"]]
    retired = [s for s in retail if s["retired"]]
    live = [s for s in retail if s["live"]]
    trainable = [s for s in retail if s["observed_lifespan_months"]]
    with_rrp = [s for s in retail if s["rrp"].get("uk")]
    with_ean = [s for s in sets if s["ean"]]
    upgraded = [s for s in sets
                if s["tracked"] and s["retirement_source"] == "brickset-uk"]

    log.info("=" * 64)
    log.info("wrote %s (%.1f MB)", OUT.name, OUT.stat().st_size / 1_000_000)
    log.info("all sets                 : %d", len(sets))
    log.info("retail sets              : %d", len(retail))
    log.info("  retired (real UK date) : %d", len(retired))
    log.info("  live (estimate needed) : %d", len(live))
    log.info("  trainable lifespans    : %d", len(trainable))
    log.info("  with UK RRP            : %d", len(with_rrp))
    log.info("with EAN (any category)  : %d", len(with_ean))
    log.info("tracked sets upgraded to a real date: %d/343", len(upgraded))
    log.info("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
