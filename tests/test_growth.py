from datetime import date

import config
from model import growth as G

UK = config.market("uk")
US = config.market("us")


def test_rate_within_bounds_for_every_theme():
    for theme in G.BASE_RATE:
        for rrp in (5, 45, 200, 700):
            for flags in ([], ["d2c", "icon", "lic"], ["sat", "new"]):
                rate, _ = G.growth_rate(theme, rrp, flags, UK)
                assert 0.015 <= rate <= 0.20, (theme, rrp, flags, rate)


def test_exclusive_beats_saturated():
    excl, _ = G.growth_rate("Icons", 200, ["d2c"], UK)
    sat, _ = G.growth_rate("Icons", 200, ["sat"], UK)
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
    assert G.net_proceeds(gross, 8.99, UK) < 8.99


def test_grade_boundaries():
    assert G.grade(0.13) == "A"
    assert G.grade(0.09) == "B"
    assert G.grade(0.05) == "C"
    assert G.grade(-0.01) == "F"
    assert G.grade(None) == "F"


# --- market awareness ------------------------------------------------------

def test_band_labels_use_market_currency():
    _, uk_label = G.rrp_band_adj(10, UK)
    _, us_label = G.rrp_band_adj(10, US)
    assert "£" in uk_label and "$" not in uk_label
    assert "$" in us_label and "£" not in us_label


def test_bands_are_market_specific_not_shared():
    """$22 is a small set in the US but mid-band in the UK. Same number,
    different band, because the thresholds differ per market."""
    uk_adj, _ = G.rrp_band_adj(22, UK)   # >= 20 -> neutral band
    us_adj, _ = G.rrp_band_adj(22, US)   # < 25  -> small-set upside
    assert uk_adj == 0.000
    assert us_adj == 0.010


def test_fees_and_shipping_differ_by_market():
    assert G.selling_fee(UK) != G.selling_fee(US)
    assert G.shipping_cost(500, UK) == 16.00   # UK cap
    assert G.shipping_cost(500, US) == 20.00   # US cap


def test_net_proceeds_respects_market_fee():
    uk = G.net_proceeds(1000, 100, UK)
    us = G.net_proceeds(1000, 100, US)
    assert uk > us   # lower UK fee and cheaper postage
