"""Rebrickable image fetching, tested against fixtures, never the network.

The JSON fixture below is the real response captured live against the
Rebrickable API on 10 September 2026 (GET /lego/sets/75192-1/) -- not
invented. If Rebrickable ever changes their response shape, that capture is
what should be refreshed, the same way tests/fixtures/ works for the price
sources.
"""
import json
from io import BytesIO
from pathlib import Path

import pytest

from collector.images import ImageError, RebrickableImages

REAL_SET_RESPONSE = {
    "set_num": "75192-1",
    "name": "Millennium Falcon",
    "year": 2017,
    "theme_id": 171,
    "num_parts": 7541,
    "set_img_url": "https://cdn.rebrickable.com/media/sets/75192-1/30881.jpg",
    "set_url": "https://rebrickable.com/sets/75192-1/millennium-falcon/",
    "last_modified_dt": "2021-11-27T08:23:26.191796Z",
}


def _tiny_jpeg_bytes() -> bytes:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1200, 900), color=(200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, *, json_body=None, content=b"", status_code=200):
        self._json_body = json_body
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Maps URLs to canned responses; records every call for assertions."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []
        self.headers = {}

    def get(self, url, timeout=None):
        self.calls.append(url)
        if url in self.responses:
            return self.responses[url]
        return FakeResponse(status_code=404)


def test_lookup_image_url_parses_real_response():
    url = "https://rebrickable.com/api/v3/lego/sets/75192-1/"
    session = FakeSession({url: FakeResponse(json_body=REAL_SET_RESPONSE)})
    fetcher = RebrickableImages("fake-key", session=session)
    assert fetcher.lookup_image_url("75192") == (
        "https://cdn.rebrickable.com/media/sets/75192-1/30881.jpg")


def test_lookup_image_url_returns_none_on_404():
    session = FakeSession({})   # nothing configured -> every URL 404s
    fetcher = RebrickableImages("fake-key", session=session)
    assert fetcher.lookup_image_url("00000") is None


def test_fetch_all_skips_files_already_on_disk(tmp_path):
    out_dir = tmp_path / "sets"
    out_dir.mkdir()
    (out_dir / "75192.jpg").write_bytes(b"already here")

    session = FakeSession({})   # would 404 if actually called
    fetcher = RebrickableImages("fake-key", session=session)
    manifest = fetcher.fetch_all(["75192"], out_dir)

    assert manifest["75192"] == "sets/75192.jpg"
    assert session.calls == []   # never hit the network for a cached file


def test_fetch_all_downloads_and_resizes_a_new_image(tmp_path):
    out_dir = tmp_path / "sets"
    lookup_url = "https://rebrickable.com/api/v3/lego/sets/75192-1/"
    img_url = REAL_SET_RESPONSE["set_img_url"]
    session = FakeSession({
        lookup_url: FakeResponse(json_body=REAL_SET_RESPONSE),
        img_url: FakeResponse(content=_tiny_jpeg_bytes()),
    })
    fetcher = RebrickableImages("fake-key", session=session)
    manifest = fetcher.fetch_all(["75192"], out_dir)

    assert manifest == {"75192": "sets/75192.jpg"}
    dest = out_dir / "75192.jpg"
    assert dest.exists()

    from PIL import Image
    with Image.open(dest) as img:
        # Source was 1200x900; MAX_DIMENSION=800 must shrink it, preserving
        # the aspect ratio rather than distorting or upscaling.
        assert max(img.size) <= 800
        assert img.size[0] / img.size[1] == pytest.approx(1200 / 900, rel=0.01)


def test_fetch_all_is_isolated_per_set(tmp_path):
    """One set with no image must not stop the rest of the batch."""
    out_dir = tmp_path / "sets"
    lookup_url = "https://rebrickable.com/api/v3/lego/sets/75192-1/"
    img_url = REAL_SET_RESPONSE["set_img_url"]
    session = FakeSession({
        lookup_url: FakeResponse(json_body=REAL_SET_RESPONSE),
        img_url: FakeResponse(content=_tiny_jpeg_bytes()),
        # "00000-1" is deliberately unconfigured -> 404 -> no image
    })
    fetcher = RebrickableImages("fake-key", session=session)
    manifest = fetcher.fetch_all(["00000", "75192"], out_dir)

    assert manifest == {"75192": "sets/75192.jpg"}


def test_rebrickable_images_requires_an_api_key():
    with pytest.raises(ValueError):
        RebrickableImages("")
