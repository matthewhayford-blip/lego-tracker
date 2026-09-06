"""Turn many sources' quotes into one best price per set, per market."""
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
    """Cheapest in-stock quote per set, grouped by market.

    Returns {market_code: {set_number: {...}}}. Prices are only ever compared
    within a market -- comparing a GBP quote with a USD one would be
    meaningless, and doing it by accident is exactly the bug this shape
    prevents.
    """
    by_market = defaultdict(lambda: defaultdict(list))
    for q in quotes:
        by_market[q.market][q.set_number].append(q)

    out: dict = {}
    for mkt, by_set in by_market.items():
        market_out = {}
        for setnum, qs in by_set.items():
            in_stock = [q for q in qs if q.in_stock]
            pool = in_stock or qs
            best = min(pool, key=lambda q: q.price)
            market_out[setnum] = {
                "best": best.to_json(),
                "all": sorted((q.to_json() for q in qs), key=lambda d: d["price"]),
                "retailer_count": len({q.retailer for q in qs}),
                "any_in_stock": bool(in_stock),
            }
        out[mkt] = market_out
    return out


def write(prices: dict, data_dir: str = "data") -> tuple[Path, Path]:
    """Write current.json and append today's snapshot to history.

    `prices` is the {market: {set_number: ...}} structure from best_per_set.
    """
    root = Path(data_dir)
    (root / "prices" / "history").mkdir(parents=True, exist_ok=True)

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "markets": {m: len(sets) for m, sets in prices.items()},
        "prices": prices,
    }
    current = root / "prices" / "current.json"
    current.write_text(json.dumps(payload, indent=1, sort_keys=True))

    snapshot = root / "prices" / "history" / f"{date.today().isoformat()}.json"
    snapshot.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    total = sum(len(s) for s in prices.values())
    log.info("wrote %d set-prices across %d market(s) to %s and %s",
             total, len(prices), current, snapshot)
    return current, snapshot


def load_current(data_dir: str = "data", market: str | None = None) -> dict:
    """Load current prices.

    With `market`, returns that market's {set_number: ...} mapping.
    Without, returns the full {market: {set_number: ...}} structure.
    """
    p = Path(data_dir) / "prices" / "current.json"
    if not p.exists():
        return {}
    prices = json.loads(p.read_text()).get("prices", {})
    if market is None:
        return prices
    return prices.get(market, {})
