"""Lifespan model: the behaviour that makes it different from a lookup table.

The point of this model is conditioning on age. A set that has already been on
sale 22 months must not be told it will retire at 19 months, because that
prediction has already been falsified by the set's own existence. These tests
pin that, plus the fallback chain and the refusal to guess from thin data.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model import lifespan as L  # noqa: E402


def mk(theme, months, group="G", last_year=2024, retail=True):
    return {
        "is_retail": retail,
        "theme": theme,
        "theme_group": group,
        "observed_lifespan_months": months,
        "uk_last_available": f"{last_year}-06-01",
    }


# 40 sets in theme A clustered around 20 months
SAMPLE = ([mk("A", 18 + (i % 5)) for i in range(40)] +
          [mk("B", 40 + (i % 7)) for i in range(40)])


def test_train_groups_by_theme():
    m = L.train(SAMPLE)
    assert len(m["by_theme"]["A"]) == 40
    assert len(m["by_theme"]["B"]) == 40
    assert m["n"] == 80


def test_train_excludes_old_retirements():
    """Pre-cutoff retirements reflect different LEGO practice and are dropped."""
    old = [mk("A", 5, last_year=2015) for _ in range(30)]
    m = L.train(SAMPLE + old)
    assert len(m["by_theme"]["A"]) == 40      # the 30 old ones excluded


def test_train_excludes_non_retail():
    m = L.train(SAMPLE + [mk("A", 99, retail=False) for _ in range(20)])
    assert all(v < 50 for v in m["by_theme"]["A"])


def test_estimate_uses_own_theme_when_sample_is_big_enough():
    m = L.train(SAMPLE)
    e = L.estimate(m, "2024-01-01", theme="A", group="G",
                   today=date(2024, 2, 1))
    assert e["basis"] == "theme:A"
    assert e["sample_size"] == 40


def test_estimate_falls_back_to_group_then_global():
    m = L.train(SAMPLE)
    e = L.estimate(m, "2024-01-01", theme="Nonexistent", group="G",
                   today=date(2024, 2, 1))
    assert e["basis"] == "group:G"

    e2 = L.estimate(m, "2024-01-01", theme="Nope", group="AlsoNope",
                    today=date(2024, 2, 1))
    assert e2["basis"] == "global"
    assert e2["confidence"] == "low"


def test_surviving_longer_raises_the_predicted_total_lifespan():
    """The core behaviour, and the reason this is a survival model.

    Two sets in the same theme, one launched a year earlier. Comparing their
    absolute window dates proves nothing -- the older one started earlier, so
    of course its window falls earlier. What must hold is that the set which
    has already survived longer is predicted to live longer IN TOTAL, because
    the short lifespans in the sample have been ruled out by its own survival.
    """
    m = L.train(SAMPLE)
    today = date(2026, 1, 1)
    young = L.estimate(m, "2025-06-01", theme="A", group="G", today=today)
    old = L.estimate(m, "2024-06-01", theme="A", group="G", today=today)

    assert young["age_months"] < old["age_months"]
    young_total = young["age_months"] + young["likeliest"]
    old_total = old["age_months"] + old["likeliest"]
    assert old_total >= young_total
    # and the older set has fewer comparable survivors left to learn from
    assert old["survivors"] <= young["survivors"]


def test_set_that_outlived_the_sample_is_flagged_not_guessed():
    """Rather than extrapolate from a handful of survivors, say so."""
    m = L.train(SAMPLE)
    e = L.estimate(m, "2014-01-01", theme="A", group="G",
                   today=date(2026, 1, 1))     # ~144 months, beyond everything
    assert e["overdue"] is True
    assert e["likeliest"] is None
    assert e["confidence"] == "low"


def test_remaining_life_is_never_negative():
    m = L.train(SAMPLE)
    e = L.estimate(m, "2024-01-01", theme="A", group="G",
                   today=date(2025, 7, 1))     # ~18 months, mid-sample
    for k in ("earliest", "likeliest", "latest"):
        if e[k] is not None:
            assert e[k] >= 0


def test_window_is_ordered():
    m = L.train(SAMPLE)
    e = L.estimate(m, "2025-01-01", theme="A", group="G",
                   today=date(2025, 6, 1))
    assert e["earliest"] <= e["likeliest"] <= e["latest"]
    assert e["window_start"] <= e["window_end"]


def test_bad_or_future_dates_return_none():
    m = L.train(SAMPLE)
    assert L.estimate(m, "not-a-date", theme="A") is None
    assert L.estimate(m, None, theme="A") is None
    assert L.estimate(m, "2030-01-01", theme="A",
                      today=date(2026, 1, 1)) is None    # not launched yet


def test_quantile_endpoints():
    v = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert L._quantile(v, 0.0) == 1.0
    assert L._quantile(v, 1.0) == 5.0
    assert L._quantile(v, 0.5) == 3.0
    assert L._quantile([7.0], 0.5) == 7.0
