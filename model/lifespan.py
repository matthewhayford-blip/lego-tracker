"""Estimate when a live set will retire, fitted to observed UK lifespans.

This is the first model in the project that can be checked against reality.
The growth model asserts rates nobody can verify for years; this one trains on
7,800 sets whose UK launch and retirement dates are both known, and can be
backtested by holding out recent retirements.

Three design decisions, each costing accuracy if skipped:

**Train on recent retirements only.** Sets retired before 2019 lasted a median
of 14.6 months; those retired since, 19.1. LEGO's behaviour changed, so old
retirements bias the estimate downwards. Default cutoff 2019.

**Condition on age already survived.** A set 22 months old has already outlived
the median, so the unconditional distribution is the wrong answer -- it would
predict a retirement that has demonstrably not happened. Instead we take the
observed lifespans *longer than its current age* and read the remaining life
from those. This is the empirical survival function, and it is the difference
between "most sets go by 19 months" and "sets that reach 22 months go by 31".

**Fall back explicitly, and say so.** Theme, then theme group, then global.
A thin theme produces a wide, low-confidence estimate rather than a confident
wrong one.

Output is a window, never a date. The input data does not support a date.
"""
from __future__ import annotations

from datetime import date, timedelta

# A theme needs this many observed lifespans before it is fitted on its own.
MIN_SAMPLE = 20
# Retirements before this year reflect different LEGO practice.
TRAIN_FROM_YEAR = 2019
DAYS_PER_MONTH = 30.44


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("no values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    i = q * (len(sorted_values) - 1)
    lo = int(i)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = i - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def train(sets, train_from_year: int = TRAIN_FROM_YEAR) -> dict:
    """Build lifespan samples keyed by theme and by theme group.

    `sets` are joined records; only retail sets with an observed lifespan and a
    recent enough retirement are used.
    """
    by_theme: dict[str, list[float]] = {}
    by_group: dict[str, list[float]] = {}
    everything: list[float] = []

    for s in sets:
        if not s.get("is_retail"):
            continue
        months = s.get("observed_lifespan_months")
        last = s.get("uk_last_available")
        if not months or not last:
            continue
        try:
            if date.fromisoformat(last).year < train_from_year:
                continue
        except ValueError:
            continue
        everything.append(months)
        if s.get("theme"):
            by_theme.setdefault(s["theme"], []).append(months)
        if s.get("theme_group"):
            by_group.setdefault(s["theme_group"], []).append(months)

    for d in (by_theme, by_group):
        for v in d.values():
            v.sort()
    everything.sort()

    return {"by_theme": by_theme, "by_group": by_group, "global": everything,
            "trained_from": train_from_year, "n": len(everything)}


def _sample_for(model: dict, theme, group) -> tuple[list[float], str, str]:
    """Pick the narrowest sample with enough data. Returns (sample, basis, confidence)."""
    t = model["by_theme"].get(theme or "", [])
    if len(t) >= MIN_SAMPLE:
        return t, f"theme:{theme}", ("high" if len(t) >= 60 else "medium")
    g = model["by_group"].get(group or "", [])
    if len(g) >= MIN_SAMPLE:
        return g, f"group:{group}", "medium" if len(g) >= 60 else "low"
    return model["global"], "global", "low"


def estimate(model: dict, first_available: str, theme=None, group=None,
             today: date | None = None) -> dict | None:
    """Estimated retirement window for a set still on sale.

    Returns None when there is nothing to estimate from.
    """
    today = today or date.today()
    try:
        start = date.fromisoformat(first_available)
    except (ValueError, TypeError):
        return None

    age = (today - start).days / DAYS_PER_MONTH
    if age < 0:
        return None

    sample, basis, confidence = _sample_for(model, theme, group)
    if not sample:
        return None

    # Conditional survival: only sets that lived at least as long as this one
    # tell us anything about what happens next.
    survivors = [m for m in sample if m >= age]

    if len(survivors) < 5:
        # Outlived almost everything comparable. Say that, rather than
        # inventing a date from three data points.
        return {
            "basis": basis,
            "confidence": "low",
            "sample_size": len(sample),
            "survivors": len(survivors),
            "age_months": round(age, 1),
            "overdue": True,
            "note": "already outlived almost all comparable sets",
            "earliest": None, "likeliest": None, "latest": None,
            "window_start": None, "window_end": None,
        }

    p25, p50, p75 = (_quantile(survivors, q) for q in (0.25, 0.50, 0.75))
    to_date = lambda m: (start + timedelta(days=m * DAYS_PER_MONTH)).isoformat()

    return {
        "basis": basis,
        "confidence": confidence,
        "sample_size": len(sample),
        "survivors": len(survivors),
        "age_months": round(age, 1),
        "overdue": False,
        # remaining life, in months from today
        "earliest": round(max(0.0, p25 - age), 1),
        "likeliest": round(max(0.0, p50 - age), 1),
        "latest": round(max(0.0, p75 - age), 1),
        # and as dates
        "window_start": to_date(p25),
        "window_end": to_date(p75),
    }


def backtest(sets, holdout_from_year: int = 2025,
             train_from_year: int = TRAIN_FROM_YEAR) -> dict:
    """Train on earlier retirements, predict ones we already know the answer to.

    The honest check: how wrong is this model, in months? Without this number
    the estimates are just assertions with more arithmetic behind them.
    """
    train_rows, test_rows = [], []
    for s in sets:
        if not (s.get("is_retail") and s.get("observed_lifespan_months")):
            continue
        last = s.get("uk_last_available")
        if not last:
            continue
        try:
            y = date.fromisoformat(last).year
        except ValueError:
            continue
        (test_rows if y >= holdout_from_year else train_rows).append(s)

    model = train(train_rows, train_from_year=train_from_year)
    errors, naive_errors = [], []
    naive = model["global"]
    naive_median = _quantile(naive, 0.5) if naive else 0

    for s in test_rows:
        first = s.get("uk_first_available")
        actual_end = s.get("uk_last_available")
        if not (first and actual_end):
            continue
        try:
            start = date.fromisoformat(first)
        except ValueError:
            continue
        # Predict from the set's own launch, as we would have at the time.
        est = estimate(model, first, s.get("theme"), s.get("theme_group"),
                       today=start)
        if not est or est["likeliest"] is None:
            continue
        predicted = est["likeliest"]
        actual = s["observed_lifespan_months"]
        errors.append(abs(predicted - actual))
        naive_errors.append(abs(naive_median - actual))

    med = lambda v: sorted(v)[len(v) // 2] if v else None
    return {
        "trained_on": len(train_rows),
        "tested_on": len(errors),
        "median_abs_error_months": round(med(errors), 1) if errors else None,
        "naive_median_abs_error_months": (round(med(naive_errors), 1)
                                          if naive_errors else None),
    }
