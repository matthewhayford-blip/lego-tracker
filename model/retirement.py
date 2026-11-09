"""Decide what we actually know about a set's retirement, and how well.

Three sources, in descending order of trust:

1. **Brickset UK `dateLastAvailable`** — LEGO's own store stopped selling it on
   this date. Not an estimate. Only exists for sets that have already retired.
2. **A fitted estimate** from `model/lifespan.py` — a window with a confidence
   level, for sets still on sale.
3. **Fan-media reporting** — the original 343-set compilation, two month-end
   buckets. Kept only as a last resort.

The point of this module is that the site should never present these three as
if they were the same thing. A real date reads as a date; an estimate reads as
a window with its confidence attached; a fan-media bucket stays vague. Collapsing
them into one "retirement_date" field is how the project previously ended up
claiming 297 sets would retire on 31 December.

Returns a dict with a `kind` the templates switch on:
    "actual"   — it has retired, on this date
    "estimate" — still on sale, likely window
    "overdue"  — still on sale, outlived its comparables, no number given
    "reported" — fan-media only
    None       — we know nothing
"""
from __future__ import annotations

from datetime import date

MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def _month_year(d: date) -> str:
    return f"{MONTHS[d.month]} {d.year}"


def _window_phrase(start: date, end: date) -> tuple[str, str, str]:
    """Human phrasing for a window, plus a slug to group by.

    Grouped by the month the window is centred on, because a listing needs one
    bucket per set and the midpoint is the least misleading choice.
    """
    mid = start + (end - start) / 2
    if start.year == end.year and start.month == end.month:
        return (f"{_month_year(start)}", f"{MONTHS[start.month][:3]} {start.year}",
                f"{MONTHS[start.month].lower()}-{start.year}")
    if (end - start).days <= 200:
        return (f"between {_month_year(start)} and {_month_year(end)}",
                f"{MONTHS[start.month][:3]}–{MONTHS[end.month][:3]} {end.year}",
                f"{MONTHS[mid.month].lower()}-{mid.year}")
    return (f"between {_month_year(start)} and {_month_year(end)}",
            f"{start.year}–{end.year}" if start.year != end.year
            else f"{MONTHS[start.month][:3]} {start.year}",
            f"{MONTHS[mid.month].lower()}-{mid.year}")


def resolve(set_number: str, tracked: dict, full: dict | None,
            estimate: dict | None, today: date | None = None) -> dict | None:
    """Best available retirement information for one set."""
    today = today or date.today()
    full = full or {}

    # --- 1. it has already retired, and we know when -----------------------
    actual = full.get("uk_last_available")
    if actual:
        try:
            d = date.fromisoformat(actual)
        except ValueError:
            d = None
        if d:
            return {
                "kind": "actual",
                "date": d,
                "long": f"{d.day} {MONTHS[d.month]} {d.year}",
                "short": f"{d.day} {MONTHS[d.month][:3]} {d.year}",
                "slug": f"{MONTHS[d.month].lower()}-{d.year}",
                "source": "brickset-uk",
                "confidence": "actual",
                "is_estimate": False,
                "retired": True,
                "days_out": (d - today).days,
            }

    # --- 2. still on sale, with a fitted estimate --------------------------
    if estimate:
        if estimate.get("overdue"):
            return {
                "kind": "overdue",
                "date": None,
                "long": "overdue — it has outlived almost every comparable set",
                "short": "Overdue",
                "slug": "overdue",
                "source": "model",
                "confidence": "low",
                "is_estimate": True,
                "retired": False,
                "days_out": None,
                "age_months": estimate.get("age_months"),
                "survivors": estimate.get("survivors"),
            }
        ws, we = estimate.get("window_start"), estimate.get("window_end")
        if ws and we:
            try:
                start, end = date.fromisoformat(ws), date.fromisoformat(we)
            except ValueError:
                start = end = None
            if start and end:
                # A window that has already begun starts from today, not from a
                # date in the past -- "between March 2024 and July 2027" on a
                # set still for sale in November 2026 reads as broken.
                if start < today:
                    start = today
                long_p, short_p, slug = _window_phrase(start, end)
                return {
                    "kind": "estimate",
                    "date": None,
                    "window_start": start,
                    "window_end": end,
                    "long": long_p,
                    "short": short_p,
                    "slug": slug,
                    "source": "model",
                    "confidence": estimate.get("confidence", "low"),
                    "basis": estimate.get("basis"),
                    "sample_size": estimate.get("sample_size"),
                    "survivors": estimate.get("survivors"),
                    "is_estimate": True,
                    "retired": False,
                    "days_out": (start - today).days,
                    "months_min": estimate.get("earliest"),
                    "months_likely": estimate.get("likeliest"),
                    "months_max": estimate.get("latest"),
                }

    # --- 3. fan-media reporting, the old behaviour -------------------------
    reported = tracked.get("retirement_date")
    if reported:
        try:
            d = date.fromisoformat(reported)
        except ValueError:
            return None
        if d.month == 12:
            long_p, short_p, slug = f"the end of {d.year}", f"End {d.year}", f"end-{d.year}"
        elif d.month <= 4:
            long_p, short_p, slug = f"early {d.year}", f"Early {d.year}", f"early-{d.year}"
        elif d.month <= 8:
            long_p, short_p, slug = f"mid-{d.year}", f"Mid {d.year}", f"mid-{d.year}"
        else:
            long_p, short_p, slug = f"late {d.year}", f"Late {d.year}", f"late-{d.year}"
        return {
            "kind": "reported",
            "date": d,
            "long": long_p, "short": short_p, "slug": slug,
            "source": tracked.get("retirement_source", "fan-media"),
            "confidence": "reported",
            "is_estimate": True,
            "retired": False,
            "days_out": (d - today).days,
        }

    return None


def summarise(resolved: list[dict]) -> dict:
    """Counts by kind, for the build log. A sharp drop in 'actual' or
    'estimate' between runs means an upstream import broke."""
    out = {}
    for r in resolved:
        if r:
            out[r["kind"]] = out.get(r["kind"], 0) + 1
    return out
