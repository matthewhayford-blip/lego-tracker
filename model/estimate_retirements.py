#!/usr/bin/env python3
"""Fit the lifespan model and write a retirement estimate for every live set.

Writes data/retirement_estimates.json, which the site build reads. The file
carries its own backtest results, so the measured error travels with the
estimates rather than living in a commit message nobody reads. If the model
ever gets worse, that shows up in the diff.

    python -m model.estimate_retirements
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import lifespan as L  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("estimate")

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "sets_full.json"
OUT = ROOT / "data" / "retirement_estimates.json"


def measure(sets, model, holdout_year=2025) -> list[dict]:
    """Backtest at several points through a set's life.

    Evaluating only at launch understates the model badly: conditioning on age
    is where the accuracy comes from, and at launch there is no age to condition
    on. The product looks sets up mid-life, so that is what gets measured.
    """
    from datetime import timedelta
    test = []
    for s in sets:
        if not (s.get("is_retail") and s.get("observed_lifespan_months")):
            continue
        last = s.get("uk_last_available")
        if not last:
            continue
        try:
            if date.fromisoformat(last).year >= holdout_year:
                test.append(s)
        except ValueError:
            continue

    naive_median = L._quantile(model["global"], 0.5) if model["global"] else 0
    rows = []
    for frac in (0.25, 0.50, 0.75):
        errs, naive = [], []
        for s in test:
            actual = s["observed_lifespan_months"]
            try:
                start = date.fromisoformat(s["uk_first_available"])
            except (ValueError, TypeError):
                continue
            age = actual * frac
            est = L.estimate(model, s["uk_first_available"], s.get("theme"),
                             s.get("theme_group"),
                             today=start + timedelta(days=age * L.DAYS_PER_MONTH))
            if not est or est.get("likeliest") is None:
                continue
            remaining = actual - age
            errs.append(abs(est["likeliest"] - remaining))
            naive.append(abs(max(0.0, naive_median - age) - remaining))
        med = lambda v: round(sorted(v)[len(v) // 2], 1) if v else None
        rows.append({"observed_at_pct_of_life": int(frac * 100),
                     "n": len(errs),
                     "median_abs_error_months": med(errs),
                     "naive_median_abs_error_months": med(naive)})
    return rows


def main() -> int:
    if not IN.exists():
        log.error("%s missing — run collector/join.py first", IN.name)
        return 1

    sets = json.loads(IN.read_text())["sets"]

    # Backtest on a model trained WITHOUT the holdout years, so the reported
    # error is honest. The published estimates use everything.
    holdout = 2025
    # NB: .get(key, default) returns None when the key is present but null,
    # which it is for every set still on sale. `or` is what is wanted here.
    def retired_before(s, year):
        v = s.get("uk_last_available") or ""
        return v[:4].isdigit() and int(v[:4]) < year

    pre = [s for s in sets if retired_before(s, holdout)]
    backtest = measure(sets, L.train(pre), holdout_year=holdout)

    model = L.train(sets)
    log.info("trained on %d lifespans from %d; %d themes fitted individually",
             model["n"], model["trained_from"],
             sum(1 for v in model["by_theme"].values() if len(v) >= L.MIN_SAMPLE))

    estimates, conf = {}, Counter()
    for s in sets:
        if not (s.get("is_retail") and s.get("live")):
            continue
        e = L.estimate(model, s.get("uk_first_available"),
                       s.get("theme"), s.get("theme_group"))
        if not e:
            continue
        estimates[s["set_number"]] = e
        conf[("overdue" if e["overdue"] else e["confidence"])] += 1

    OUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trained_from_year": model["trained_from"],
        "training_sample": model["n"],
        "min_sample_for_theme": L.MIN_SAMPLE,
        "backtest": backtest,
        "estimate_count": len(estimates),
        "confidence_breakdown": dict(conf),
        "estimates": estimates,
    }, indent=1))

    log.info("=" * 60)
    log.info("wrote %s", OUT.name)
    log.info("estimates: %d   %s", len(estimates), dict(conf))
    for r in backtest:
        log.info("  at %2d%% of life: %s months (naive %s) on n=%d",
                 r["observed_at_pct_of_life"], r["median_abs_error_months"],
                 r["naive_median_abs_error_months"], r["n"])
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
