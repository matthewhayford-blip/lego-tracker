#!/usr/bin/env python3
"""Import UK RRP, real retirement dates and barcodes from the Brickset API.

This is the highest-value import in the rebuild, because Brickset carries three
things Rebrickable does not, and one of them we had written off as unobtainable.

    LEGOCom.UK.retailPrice           RRP in GBP -- the baseline for every
                                     retired-set performance calculation
    LEGOCom.UK.dateLastAvailable     the date LEGO.com UK STOPPED selling it
    LEGOCom.UK.dateFirstAvailable    and started
    barcode.EAN / barcode.UPC        the scanner's lookup table
    launchDate / exitDate            Brickset's own overall availability dates

`dateLastAvailable` is the important one. The project has been treating
retirement dates as unknowable and using two fan-media buckets for 343 sets
("the end of 2026"). This is an actual per-set date, per market, derived from
LEGO's own store. For sets that have already retired it is the real answer; for
sets still on sale it is absent, which is exactly the population the estimation
model is for -- and these observed dates are what that model gets fitted to.

Keyed on the bare set number to join with catalogue.json and sets.json.

Needs BRICKSET_API_KEY (free, from brickset.com/tools/webservices/requestkey).
Only getSets counts against the daily key quota, and the whole catalogue is
roughly 50-80 calls at pageSize 500, so a full import is cheap.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("brickset")

API = "https://brickset.com/api/v3.asmx/getSets"
PAGE_SIZE = 500          # API maximum
PAUSE = 1.0              # between calls; we are a guest here
FIRST_YEAR = 1990
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "brickset.json"
UA = "RetiredAndRareBot/0.1 (+https://retiredandrare.com)"


class BricksetError(RuntimeError):
    pass


def iso_date(value):
    """Brickset dates arrive as ISO-ish strings; keep the date, drop the time."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(value)[:10] or None


def extract(raw: dict) -> dict:
    """One API set record -> the fields we actually store."""
    uk = (raw.get("LEGOCom") or {}).get("UK") or {}
    bar = raw.get("barcode") or {}
    number = str(raw.get("number") or "").strip()

    return {
        "set_number": number,
        "number_variant": raw.get("numberVariant"),
        "brickset_id": raw.get("setID"),
        "name": raw.get("name"),
        "year": raw.get("year"),
        "theme": raw.get("theme"),
        "subtheme": raw.get("subtheme") or None,
        "theme_group": raw.get("themeGroup") or None,
        "category": raw.get("category") or None,
        "pieces": raw.get("pieces"),
        "minifigs": raw.get("minifigs"),
        "packaging": raw.get("packagingType") or None,
        "availability": raw.get("availability") or None,
        # --- the money and the dates ---
        "rrp_gbp": uk.get("retailPrice"),
        "uk_first_available": iso_date(uk.get("dateFirstAvailable")),
        "uk_last_available": iso_date(uk.get("dateLastAvailable")),
        "launch_date": iso_date(raw.get("launchDate")),
        "exit_date": iso_date(raw.get("exitDate")),
        # --- the scanner ---
        "ean": (bar.get("EAN") or "").strip() or None,
        "upc": (bar.get("UPC") or "").strip() or None,
    }


def fetch_page(key: str, params: dict, session: requests.Session) -> tuple[int, list]:
    r = session.post(API, timeout=60,
                     headers={"User-Agent": UA},
                     data={"apiKey": key, "userHash": "",
                           "params": json.dumps(params)})
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        msg = body.get("message", "unknown error")
        # These two are terminal; everything else may be transient.
        if "API key" in msg or "limit exceeded" in msg:
            raise BricksetError(msg)
        raise BricksetError(f"{msg} (params={params})")
    return int(body.get("matches", 0)), body.get("sets") or []


def fetch_year(key: str, year: int, session: requests.Session) -> list[dict]:
    """All sets for one year. Years partition the catalogue cleanly and keep
    each page well inside the 500-record cap."""
    out, page = [], 1
    while True:
        matches, rows = fetch_page(
            key, {"year": str(year), "pageSize": PAGE_SIZE, "pageNumber": page},
            session)
        out.extend(extract(r) for r in rows)
        if len(rows) < PAGE_SIZE:
            break
        page += 1
        time.sleep(PAUSE)
    return out


def main() -> int:
    key = os.environ.get("BRICKSET_API_KEY", "").strip()
    if not key:
        log.error("BRICKSET_API_KEY is not set — request one at "
                  "https://brickset.com/tools/webservices/requestkey")
        return 2

    this_year = datetime.now(timezone.utc).year
    years = range(FIRST_YEAR, this_year + 3)   # +3: forthcoming sets are listed
    session = requests.Session()

    all_sets: list[dict] = []
    for y in years:
        try:
            rows = fetch_year(key, y, session)
        except BricksetError as exc:
            if "limit exceeded" in str(exc) or "API key" in str(exc):
                log.error("stopping: %s", exc)
                break
            log.warning("year %d failed: %s", y, exc)
            continue
        all_sets.extend(rows)
        log.info("%d: %d sets (running total %d)", y, len(rows), len(all_sets))
        time.sleep(PAUSE)

    if not all_sets:
        log.error("no sets retrieved — not overwriting %s", OUT.name)
        return 1

    # Deduplicate on set_number, preferring the record with the most filled in.
    # Number variants (-1, -2) share a set_number; the richer one is the one
    # people mean.
    best: dict[str, dict] = {}
    for s in all_sets:
        n = s["set_number"]
        if not n:
            continue
        filled = sum(1 for v in s.values() if v not in (None, "", 0))
        if n not in best or filled > best[n]["_filled"]:
            best[n] = {**s, "_filled": filled}
    sets = [{k: v for k, v in s.items() if k != "_filled"}
            for s in sorted(best.values(), key=lambda s: s["set_number"])]

    with_rrp = [s for s in sets if s["rrp_gbp"]]
    with_exit = [s for s in sets if s["uk_last_available"]]
    with_both = [s for s in sets
                 if s["uk_first_available"] and s["uk_last_available"]]
    with_ean = [s for s in sets if s["ean"]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "brickset api v3",
        "set_count": len(sets),
        "sets": sets,
    }, separators=(",", ":"), ensure_ascii=False))

    log.info("=" * 64)
    log.info("wrote %s (%.1f MB)", OUT.name, OUT.stat().st_size / 1_000_000)
    log.info("sets                       : %d", len(sets))
    log.info("with UK RRP                : %d", len(with_rrp))
    log.info("with UK retirement date    : %d   <-- real dates, not estimates",
             len(with_exit))
    log.info("with BOTH UK dates         : %d   <-- trainable lifespans",
             len(with_both))
    log.info("with EAN barcode           : %d   <-- scanner lookups",
             len(with_ean))

    # The join that decides whether any of this is usable.
    tracked = json.loads((ROOT / "data" / "sets.json").read_text())
    have = {s["set_number"] for s in sets}
    log.info("our 343 tracked sets found : %d",
             sum(1 for s in tracked if s["set_number"] in have))
    log.info("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
