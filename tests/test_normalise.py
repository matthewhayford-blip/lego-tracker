from datetime import datetime, timezone
from decimal import Decimal

from collector.normalise import best_per_set
from collector.sources.base import PriceQuote


def q(setnum, retailer, price, in_stock=True, market="uk", currency="GBP"):
    return PriceQuote(set_number=setnum, retailer=retailer,
                      price=Decimal(str(price)), in_stock=in_stock,
                      url="https://example.test", source="test",
                      market=market, currency=currency,
                      seen_at=datetime.now(timezone.utc))


def test_picks_cheapest_in_stock():
    out = best_per_set([q("75192", "A", 700), q("75192", "B", 650),
                        q("75192", "C", 600, in_stock=False)])
    assert out["uk"]["75192"]["best"]["price"] == 650.0
    assert out["uk"]["75192"]["retailer_count"] == 3


def test_falls_back_to_cheapest_when_nothing_in_stock():
    out = best_per_set([q("10307", "A", 500, False), q("10307", "B", 450, False)])
    assert out["uk"]["10307"]["best"]["price"] == 450.0
    assert out["uk"]["10307"]["any_in_stock"] is False


def test_quotes_sorted_cheapest_first():
    out = best_per_set([q("21323", "A", 340), q("21323", "B", 300)])
    prices = [p["price"] for p in out["uk"]["21323"]["all"]]
    assert prices == sorted(prices)


# --- market separation -----------------------------------------------------

def test_markets_are_kept_separate():
    """The whole point: a cheaper USD number must never win a GBP comparison."""
    out = best_per_set([
        q("75192", "UK Shop", 700, market="uk", currency="GBP"),
        q("75192", "US Shop", 650, market="us", currency="USD"),
    ])
    assert set(out) == {"uk", "us"}
    assert out["uk"]["75192"]["best"]["retailer"] == "UK Shop"
    assert out["us"]["75192"]["best"]["retailer"] == "US Shop"
    assert out["uk"]["75192"]["best"]["currency"] == "GBP"
    assert out["us"]["75192"]["best"]["currency"] == "USD"


def test_quote_carries_market_and_currency_to_json():
    d = q("10307", "A", 42, market="us", currency="USD").to_json()
    assert d["market"] == "us"
    assert d["currency"] == "USD"
    assert d["price"] == 42.0
