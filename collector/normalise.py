"""Turn many sources' quotes into one best price per set, plus history."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# A quote older than this is not shown as "current".
MAX_AGE_HOURS = 72


def best_per_set(quotes) -> dict:
    """Cheapest in-stock quote per set; falls back to cheapest if none in stock."""
    by_set = defaultdict(list)
    for q in quotes:
        by_set[q.set_number].append(q)

    out = {}
    for setnum, qs in by_set.items():
        in_stock = [q for q in qs if q.in_stock]
        pool = in_stock or qs
        best = min(pool, key=lambda q: q.price_gbp)
        out[setnum] = {
            "best": best.to_json(),
            "all": sorted((q.to_json() for q in qs),
                          key=lambda d: d["price_gbp"]),
            "retailer_count": len({q.retailer for q in qs}),
            "any_in_stock": bool(in_stock),
        }
    return out


def write(prices: dict, data_dir: str = "data") -> tuple[Path, Path]:
    """Write current.json and append today's snapshot to history."""
    root = Path(data_dir)
    (root / "prices" / "history").mkdir(parents=True, exist_ok=True)

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "set_count": len(prices),
        "prices": prices,
    }
    current = root / "prices" / "current.json"
    current.write_text(json.dumps(payload, indent=1, sort_keys=True))

    snapshot = root / "prices" / "history" / f"{date.today().isoformat()}.json"
    snapshot.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    log.info("wrote %d sets to %s and %s", len(prices), current, snapshot)
    return current, snapshot


def load_current(data_dir: str = "data") -> dict:
    p = Path(data_dir) / "prices" / "current.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text()).get("prices", {})
