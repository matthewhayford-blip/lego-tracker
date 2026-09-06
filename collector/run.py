#!/usr/bin/env python3
"""Entry point for the nightly collection run.

Every source is attempted independently: one broken source degrades coverage,
it does not fail the run. The exit code is non-zero only if *every* source
failed, which is the signal that something systemic is wrong.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from collector import normalise
from collector.sources import ALL_SOURCES
from collector.sources.base import SourceError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("collector")


def tracked_set_numbers(data_dir="data") -> list[str]:
    sets = json.loads((Path(data_dir) / "sets.json").read_text())
    return [s["set_number"] for s in sets]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--limit", type=int, default=0,
                    help="only collect this many sets (for smoke tests)")
    ap.add_argument("--only", help="comma-separated source names to run")
    args = ap.parse_args()

    wanted = tracked_set_numbers(args.data_dir)
    if args.limit:
        wanted = wanted[: args.limit]
    log.info("collecting prices for %d sets", len(wanted))

    only = {s.strip() for s in args.only.split(",")} if args.only else None
    quotes, ok, failed = [], [], []

    for cls in ALL_SOURCES:
        src = cls()
        if only and src.name not in only:
            continue
        try:
            got = src.fetch(wanted)
            quotes.extend(got)
            ok.append(f"{src.name} ({len(got)})")
        except SourceError as exc:
            failed.append(src.name)
            log.error("SOURCE FAILED %s -- %s", src.name, exc)
        except Exception as exc:                       # noqa: BLE001
            failed.append(src.name)
            log.exception("SOURCE CRASHED %s -- %s", src.name, exc)

    log.info("sources ok: %s | failed: %s", ", ".join(ok) or "none",
             ", ".join(failed) or "none")

    if not quotes:
        log.error("no quotes from any source — not overwriting current.json")
        return 1

    prices = normalise.best_per_set(quotes)   # {market: {set_number: ...}}
    normalise.write(prices, args.data_dir)
    log.info("done: %d quotes -> %s",
             len(quotes),
             ", ".join(f"{m}: {len(s)} sets" for m, s in sorted(prices.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
