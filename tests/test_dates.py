"""Retirement dates must not be presented more precisely than they are known.

Our dates come from fan-media reporting and cluster on month-end buckets. If
a future data source supplies genuinely exact dates it should set
`date_precision: "exact"` per set, and these tests will allow the precise
rendering back in. Until then, day-level claims are a correctness bug, not a
copy preference.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "site"))
from build import date_phrase  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_period_dates_never_render_a_day():
    long_p, short_p, slug = date_phrase(date(2026, 12, 31), "period")
    for text in (long_p, short_p, slug):
        assert "31" not in text
        assert "December" not in text and "december" not in text
    assert long_p == "the end of 2026"


def test_exact_dates_still_render_precisely():
    long_p, short_p, slug = date_phrase(date(2026, 12, 31), "exact")
    assert long_p == "31 December 2026"
    assert slug == "december-2026"


def test_period_buckets_cover_the_year():
    seen = {date_phrase(date(2027, m, 28), "period")[0] for m in range(1, 13)}
    assert seen == {"early 2027", "mid-2027", "late 2027", "the end of 2027"}


def test_every_set_declares_its_date_precision():
    sets = json.loads((ROOT / "data" / "sets.json").read_text())
    missing = [s["set_number"] for s in sets if "date_precision" not in s]
    assert not missing, f"sets without date_precision: {missing[:5]}"


def test_current_data_is_all_estimates():
    """Guards the claim the copy makes. If a source ever supplies exact dates
    this test should be updated deliberately, not by accident."""
    sets = json.loads((ROOT / "data" / "sets.json").read_text())
    assert {s["date_precision"] for s in sets} == {"period"}
