from datetime import datetime, timezone
from decimal import Decimal

from collector.normalise import best_per_set
from collector.sources.base import PriceQuote


def q(setnum, retailer, price, in_stock=True):
    return PriceQuote(set_number=setnum, retailer=retailer,
                      price_gbp=Decimal(str(price)), in_stock=in_stock,
                      url="https://example.test", source="test",
                      seen_at=datetime.now(timezone.utc))


def test_picks_cheapest_in_stock():
    out = best_per_set([q("75192", "A", 700), q("75192", "B", 650),
                        q("75192", "C", 600, in_stock=False)])
    assert out["75192"]["best"]["price_gbp"] == 650.0
    assert out["75192"]["retailer_count"] == 3


def test_falls_back_to_cheapest_when_nothing_in_stock():
    out = best_per_set([q("10307", "A", 500, False), q("10307", "B", 450, False)])
    assert out["10307"]["best"]["price_gbp"] == 450.0
    assert out["10307"]["any_in_stock"] is False


def test_quotes_sorted_cheapest_first():
    out = best_per_set([q("21323", "A", 340), q("21323", "B", 300)])
    prices = [p["price_gbp"] for p in out["21323"]["all"]]
    assert prices == sorted(prices)
