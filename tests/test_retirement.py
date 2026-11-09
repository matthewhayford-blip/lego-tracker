"""Retirement resolution: which source wins, and how each one is phrased.

The failure this guards against is the one the project already made once —
presenting a fan-media bucket with the same confidence as a known date. Each
source must keep its own `kind`, so a template can tell them apart.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import retirement as R  # noqa: E402

TODAY = date(2026, 11, 9)

TRACKED = {"retirement_date": "2026-12-31", "retirement_source": "brickfanatics"}
RETIRED_FULL = {"uk_last_available": "2024-03-15"}
LIVE_ESTIMATE = {"window_start": "2027-02-01", "window_end": "2027-08-01",
                 "confidence": "high", "basis": "theme:Star Wars",
                 "sample_size": 120, "survivors": 48,
                 "earliest": 3.0, "likeliest": 6.0, "latest": 9.0,
                 "overdue": False}


def test_real_date_beats_everything():
    r = R.resolve("75192", TRACKED, RETIRED_FULL, LIVE_ESTIMATE, today=TODAY)
    assert r["kind"] == "actual"
    assert r["source"] == "brickset-uk"
    assert r["is_estimate"] is False
    assert r["retired"] is True
    assert r["long"] == "15 March 2024"


def test_estimate_beats_fan_media():
    r = R.resolve("75192", TRACKED, {}, LIVE_ESTIMATE, today=TODAY)
    assert r["kind"] == "estimate"
    assert r["confidence"] == "high"
    assert r["basis"] == "theme:Star Wars"
    assert r["is_estimate"] is True


def test_fan_media_is_the_last_resort():
    r = R.resolve("75192", TRACKED, {}, None, today=TODAY)
    assert r["kind"] == "reported"
    assert r["long"] == "the end of 2026"
    assert r["confidence"] == "reported"


def test_nothing_known_returns_none():
    assert R.resolve("9999", {}, {}, None, today=TODAY) is None


def test_overdue_gives_no_number():
    r = R.resolve("10281", {}, {}, {"overdue": True, "age_months": 70.2,
                                    "survivors": 3}, today=TODAY)
    assert r["kind"] == "overdue"
    assert r["date"] is None
    assert "outlived" in r["long"]


def test_window_already_begun_starts_from_today():
    """A window whose start is in the past must not be rendered as beginning
    on a date that has already gone by."""
    est = dict(LIVE_ESTIMATE, window_start="2025-01-01", window_end="2027-06-01")
    r = R.resolve("x", {}, {}, est, today=TODAY)
    assert r["window_start"] == TODAY
    assert r["days_out"] == 0


def test_short_window_inside_one_month_reads_as_that_month():
    est = dict(LIVE_ESTIMATE, window_start="2027-03-02", window_end="2027-03-28")
    r = R.resolve("x", {}, {}, est, today=TODAY)
    assert r["long"] == "March 2027"
    assert r["slug"] == "march-2027"


def test_window_spanning_months_reads_as_a_range():
    r = R.resolve("x", {}, {}, LIVE_ESTIMATE, today=TODAY)
    assert r["long"] == "between February 2027 and August 2027"
    # grouped by the midpoint month, so a listing has one bucket per set
    assert r["slug"] == "may-2027"


def test_bad_dates_do_not_raise():
    assert R.resolve("x", {"retirement_date": "nonsense"}, {}, None,
                     today=TODAY) is None
    r = R.resolve("x", TRACKED, {"uk_last_available": "nope"}, None, today=TODAY)
    assert r["kind"] == "reported"      # falls through to the valid source


def test_summarise_counts_kinds():
    rows = [R.resolve("a", TRACKED, RETIRED_FULL, None, today=TODAY),
            R.resolve("b", TRACKED, {}, LIVE_ESTIMATE, today=TODAY),
            R.resolve("c", TRACKED, {}, None, today=TODAY),
            None]
    assert R.summarise(rows) == {"actual": 1, "estimate": 1, "reported": 1}
