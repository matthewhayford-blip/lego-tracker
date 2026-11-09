"""Catalogue import: the transformations, not the download.

The network fetch runs in CI; what is worth testing here is the shape of what
comes out -- theme nesting resolved to a root, junk rows excluded, and the set
number keyed in the form the rest of the project joins on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.catalogue import slugify, theme_lookup  # noqa: E402


THEMES = [
    {"id": "158", "name": "Star Wars", "parent_id": ""},
    {"id": "171", "name": "Episode IV-VI", "parent_id": "158"},
    {"id": "209", "name": "Ultimate Collector Series", "parent_id": "171"},
    {"id": "52", "name": "Town", "parent_id": ""},
    {"id": "67", "name": "City", "parent_id": "52"},
]


def test_nested_theme_resolves_to_root():
    t = theme_lookup(THEMES)
    detail, root = t["209"]
    assert detail == "Ultimate Collector Series"
    assert root == "Star Wars"          # three levels up


def test_top_level_theme_is_its_own_root():
    assert theme_lookup(THEMES)["158"] == ("Star Wars", "Star Wars")


def test_one_level_nesting():
    assert theme_lookup(THEMES)["67"] == ("City", "Town")


def test_unknown_theme_id_does_not_raise():
    t = theme_lookup(THEMES)
    assert "9999" not in t


def test_theme_cycle_terminates():
    """Rebrickable data has contained parent cycles. A depth guard means a bad
    row degrades to a wrong name, not a hung import."""
    cyclic = [{"id": "1", "name": "A", "parent_id": "2"},
              {"id": "2", "name": "B", "parent_id": "1"}]
    t = theme_lookup(cyclic)          # must return, not recurse forever
    assert set(t) == {"1", "2"}


def test_slugify_handles_real_set_names():
    assert slugify("Millennium Falcon (UCS)") == "millennium-falcon-ucs"
    assert slugify("Jabba's Sail Barge") == "jabbas-sail-barge"
    assert slugify("Café Corner") == "cafe-corner"
    assert slugify("X-Wing Starfighter™") == "x-wing-starfighter"
    assert slugify("10497") == "10497"


def test_slugify_never_returns_empty():
    assert slugify("") == "set"
    assert slugify("!!!") == "set"
