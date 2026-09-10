#!/usr/bin/env python3
"""Entry point for the (manual, occasional) image backfill run.

Unlike collector/run.py this is not part of the nightly refresh -- box art
doesn't go stale the way a price does. Run it by hand, or from the
fetch-images workflow, whenever new sets are added to data/sets.json.
Already-downloaded images are skipped, so re-running only fetches what's new.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from collector.images import RebrickableImages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("fetch_images")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--limit", type=int, default=0,
                     help="only fetch this many sets (for smoke tests)")
    args = ap.parse_args()

    api_key = os.environ.get("REBRICKABLE_API_KEY")
    if not api_key:
        log.error("REBRICKABLE_API_KEY not set in the environment -- "
                   "nothing to do. See HANDOVER.md for where this lives.")
        return 1

    data_dir = Path(args.data_dir)
    sets = json.loads((data_dir / "sets.json").read_text())
    wanted = [s["set_number"] for s in sets]
    if args.limit:
        wanted = wanted[: args.limit]
    log.info("fetching images for %d sets", len(wanted))

    out_dir = data_dir / "images" / "sets"
    fetcher = RebrickableImages(api_key)
    manifest = fetcher.fetch_all(wanted, out_dir)

    # Merge rather than overwrite: a --limit smoke test must not erase entries
    # a full prior run already found.
    manifest_path = data_dir / "images" / "manifest.json"
    existing = {}
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
    existing.update(manifest)
    manifest_path.write_text(json.dumps(existing, indent=1, sort_keys=True))

    log.info("wrote %s (%d sets total, %d new this run)",
              manifest_path, len(existing), len(manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
