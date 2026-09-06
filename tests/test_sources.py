"""Parser tests run against fixtures, never the network.

When a source breaks in production, the fix is: save the live HTML into
tests/fixtures/, add the case here, then fix the parser until it passes.
"""
from decimal import Decimal

from collector.sources.base import extract_json_ld, offers_from_product, parse_price

PRODUCT_PAGE = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"LEGO Millennium Falcon 75192",
 "sku":"75192","offers":{"@type":"Offer","price":"734.99","priceCurrency":"GBP",
 "availability":"https://schema.org/InStock"}}
</script></head><body></body></html>
"""

GRAPH_PAGE = """
<html><head><script type="application/ld+json">
{"@graph":[{"@type":"BreadcrumbList"},
 {"@type":"Product","sku":"10307","offers":[
   {"@type":"Offer","price":"499.99","availability":"https://schema.org/OutOfStock"}]}]}
</script></head></html>
"""


def test_parse_price_variants():
    assert parse_price("£42.99") == Decimal("42.99")
    assert parse_price("1,234.50") == Decimal("1234.50")
    assert parse_price(59.99) == Decimal("59.99")
    assert parse_price("") is None
    assert parse_price("out of stock") is None
    assert parse_price(None) is None


def test_extract_json_ld_finds_product():
    nodes = extract_json_ld(PRODUCT_PAGE)
    assert any(n.get("@type") == "Product" for n in nodes)


def test_extract_json_ld_unwraps_graph():
    nodes = extract_json_ld(GRAPH_PAGE)
    types = {n.get("@type") for n in nodes}
    assert "Product" in types and "BreadcrumbList" in types


def test_offers_reads_price_and_stock():
    product = next(n for n in extract_json_ld(PRODUCT_PAGE) if n["@type"] == "Product")
    price, in_stock = offers_from_product(product)
    assert price == Decimal("734.99") and in_stock is True


def test_offers_detects_out_of_stock():
    product = next(n for n in extract_json_ld(GRAPH_PAGE) if n.get("@type") == "Product")
    price, in_stock = offers_from_product(product)
    assert price == Decimal("499.99") and in_stock is False


def test_malformed_json_ld_does_not_raise():
    assert extract_json_ld('<script type="application/ld+json">{oops</script>') == []
