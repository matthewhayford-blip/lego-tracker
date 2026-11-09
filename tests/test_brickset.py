"""Brickset extraction: the record shape, not the network.

What matters here is that the three valuable fields survive the transform --
UK RRP, the UK availability dates, and the barcodes -- and that a set still on
sale is distinguishable from one that has retired. Getting that distinction
wrong would silently mark live sets as retired, which is worse than having no
date at all.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.brickset import extract, iso_date  # noqa: E402


RETIRED = {
    "setID": 26725, "number": "10281", "numberVariant": 1,
    "name": "Bonsai Tree", "year": 2021, "theme": "Botanical Collection",
    "themeGroup": "Model making", "subtheme": "Botanical Collection",
    "category": "Normal", "pieces": 878, "minifigs": 0,
    "packagingType": "Box", "availability": "Retail",
    "LEGOCom": {"UK": {"retailPrice": 44.99,
                       "dateFirstAvailable": "2021-01-01T00:00:00Z",
                       "dateLastAvailable": "2024-12-31T00:00:00Z"},
                "US": {"retailPrice": 49.99}},
    "barcode": {"EAN": "5702016888799", "UPC": "673419340687"},
    "launchDate": "2021-01-01T00:00:00Z",
    "exitDate": "2024-12-31T00:00:00Z",
}

STILL_ON_SALE = {
    "setID": 31200, "number": "75192", "name": "Millennium Falcon",
    "year": 2017, "theme": "Star Wars", "pieces": 7541,
    "LEGOCom": {"UK": {"retailPrice": 734.99,
                       "dateFirstAvailable": "2017-10-01T00:00:00Z",
                       "dateLastAvailable": None}},
    "barcode": {"EAN": "5702015869935", "UPC": None},
}

BARE = {"setID": 1, "number": "1234", "name": "Thing", "year": 1999}


def test_retired_set_keeps_uk_price_and_both_dates():
    s = extract(RETIRED)
    assert s["set_number"] == "10281"
    assert s["rrp_gbp"] == 44.99               # UK, not the 49.99 US price
    assert s["uk_first_available"] == "2021-01-01"
    assert s["uk_last_available"] == "2024-12-31"
    assert s["ean"] == "5702016888799"
    assert s["upc"] == "673419340687"


def test_live_set_has_no_retirement_date():
    """The whole point: absent dateLastAvailable means still on sale, and must
    not become a date."""
    s = extract(STILL_ON_SALE)
    assert s["uk_first_available"] == "2017-10-01"
    assert s["uk_last_available"] is None
    assert s["rrp_gbp"] == 734.99


def test_missing_blocks_do_not_raise():
    s = extract(BARE)
    assert s["set_number"] == "1234"
    for field in ("rrp_gbp", "uk_last_available", "ean", "upc", "launch_date"):
        assert s[field] is None


def test_empty_barcode_strings_become_none():
    s = extract({**BARE, "barcode": {"EAN": "  ", "UPC": ""}})
    assert s["ean"] is None and s["upc"] is None


def test_iso_date_trims_time():
    assert iso_date("2024-12-31T00:00:00Z") == "2024-12-31"
    assert iso_date("2024-12-31") == "2024-12-31"
    assert iso_date(None) is None
    assert iso_date("") is None


def test_iso_date_survives_unparseable_input():
    """Better a truncated string than an exception mid-import."""
    assert iso_date("not a date at all") == "not a date"


def test_lifespan_is_computable_for_retired_sets():
    """This is what the estimation model trains on."""
    from datetime import date
    s = extract(RETIRED)
    first = date.fromisoformat(s["uk_first_available"])
    last = date.fromisoformat(s["uk_last_available"])
    months = (last - first).days / 30.44
    assert 46 < months < 50          # ~4 years on sale
