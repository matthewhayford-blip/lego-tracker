from datetime import date
from model import growth as G


def test_rate_within_bounds_for_every_theme():
    for theme in G.BASE_RATE:
        for rrp in (5, 45, 200, 700):
            for flags in ([], ["d2c", "icon", "lic"], ["sat", "new"]):
                rate, _ = G.growth_rate(theme, rrp, flags)
                assert 0.015 <= rate <= 0.20, (theme, rrp, flags, rate)


def test_exclusive_beats_saturated():
    excl, _ = G.growth_rate("Icons", 200, ["d2c"])
    sat, _ = G.growth_rate("Icons", 200, ["sat"])
    assert excl > sat


def test_value_flat_until_after_retirement():
    retire = date(2027, 1, 1)
    rrp = 100.0
    # during the post-retirement clearance window, still at RRP
    assert G.projected_value(rrp, 0.12, retire, date(2027, 6, 1)) == rrp
    # well after it, appreciating
    assert G.projected_value(rrp, 0.12, retire, date(2031, 1, 1)) > rrp


def test_fees_make_cheap_sets_unprofitable():
    """A £9 set cannot clear a 14% fee plus postage. The model must say so."""
    gross = G.projected_value(8.99, 0.05, date(2026, 12, 31), date(2032, 1, 1))
    assert G.net_proceeds(gross, 8.99) < 8.99


def test_grade_boundaries():
    assert G.grade(0.13) == "A"
    assert G.grade(0.09) == "B"
    assert G.grade(0.05) == "C"
    assert G.grade(-0.01) == "F"
    assert G.grade(None) == "F"
