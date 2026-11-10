"""Which sets the collector is willing to record a price for.

This list used to be the 343 curated sets, and `fetch()` discards any quote
whose set is not in it. That quietly capped price coverage: a source could hand
us a price and we would throw it away for being off-list. Price history cannot
be backfilled, so discarding prices we have already fetched is the one mistake
with a permanent cost.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.run import tracked_set_numbers  # noqa: E402


def write(tmp_path, full=None, tracked=None):
    if full is not None:
        (tmp_path / "sets_full.json").write_text(json.dumps({"sets": full}))
    if tracked is not None:
        (tmp_path / "sets.json").write_text(json.dumps(tracked))
    return str(tmp_path)


def test_uses_full_catalogue_when_present(tmp_path):
    d = write(tmp_path,
              full=[{"set_number": "1", "is_retail": True},
                    {"set_number": "2", "is_retail": True}],
              tracked=[{"set_number": "9"}])
    assert set(tracked_set_numbers(d)) == {"1", "2"}


def test_excludes_non_retail(tmp_path):
    """Gear, books and collections are catalogue entries, not things to price."""
    d = write(tmp_path,
              full=[{"set_number": "1", "is_retail": True},
                    {"set_number": "2", "is_retail": False},
                    {"set_number": "3", "is_retail": None}],
              tracked=[{"set_number": "9"}])
    assert tracked_set_numbers(d) == ["1"]


def test_live_sets_come_first(tmp_path):
    """`--limit` must smoke-test against sets people can still buy, and a
    per-set source should spend its budget there too."""
    d = write(tmp_path, full=[
        {"set_number": "old", "is_retail": True, "year": 1999},
        {"set_number": "live", "is_retail": True, "year": 2026, "live": True},
        {"set_number": "tracked", "is_retail": True, "year": 2001,
         "tracked": True},
    ], tracked=[{"set_number": "x"}])
    assert tracked_set_numbers(d) == ["live", "tracked", "old"]


def test_newer_first_within_a_group(tmp_path):
    d = write(tmp_path, full=[
        {"set_number": "a", "is_retail": True, "year": 2020, "live": True},
        {"set_number": "b", "is_retail": True, "year": 2026, "live": True},
    ], tracked=[{"set_number": "x"}])
    assert tracked_set_numbers(d) == ["b", "a"]


def test_missing_year_does_not_raise(tmp_path):
    d = write(tmp_path, full=[
        {"set_number": "a", "is_retail": True, "live": True},
        {"set_number": "b", "is_retail": True, "year": 2026, "live": True},
    ], tracked=[{"set_number": "x"}])
    assert tracked_set_numbers(d) == ["b", "a"]


def test_falls_back_to_sets_json_without_the_join(tmp_path):
    d = write(tmp_path, tracked=[{"set_number": "343a"}, {"set_number": "343b"}])
    assert tracked_set_numbers(d) == ["343a", "343b"]


def test_falls_back_when_full_has_no_retail_sets(tmp_path):
    d = write(tmp_path,
              full=[{"set_number": "1", "is_retail": False}],
              tracked=[{"set_number": "343a"}])
    assert tracked_set_numbers(d) == ["343a"]
