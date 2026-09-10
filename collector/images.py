"""Rebrickable — official set images, the site's only licensed image source.

Every other candidate was ruled out before this one was picked (see
HANDOVER.md): lego.com blocks scraping outright, and hot-linking any
retailer's product photography has the same rights problem as scraping their
prices did. Rebrickable's API terms are explicit that commercial use is fine
("The Rebrickable API may be used for any purpose, including commercial"),
and they recommend downloading rather than hot-linking since their CDN URLs
can change -- so images are fetched once and committed to the repo, the same
"accumulates in git for free" pattern data/prices/ already uses.

This is a bulk backfill, not part of the nightly refresh: a set's box art
does not change day to day, so `fetch_images.py` is triggered manually (or on
a long cadence) rather than wired into collector/run.py. Already-downloaded
images are skipped, so re-running after new sets are added only fetches the
new ones.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

API_URL = "https://rebrickable.com/api/v3/lego/sets/{set_num}/"
REQUEST_GAP_SECONDS = 1.0   # deliberate politeness; do not lower
USER_AGENT = (
    "RetiredAndRareBot/0.1 (+https://retiredandrare.com/about) "
    "UK LEGO retirement tracker; contact: hello@retiredandrare.com"
)

# The max dimension a stored image is resized to. Set box art from Rebrickable
# is already modest in size, but this keeps the repo predictable regardless of
# what any one set's source image happens to be.
MAX_DIMENSION = 800
JPEG_QUALITY = 85


class ImageError(RuntimeError):
    """Raised when one set's image cannot be looked up or downloaded."""


class RebrickableImages:
    name = "rebrickable"

    def __init__(self, api_key: str, session=None):
        import requests
        if not api_key:
            raise ValueError("RebrickableImages requires an api_key")
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Authorization": f"key {api_key}",
        })
        self._last_request = 0.0

    def _throttle(self) -> None:
        gap = REQUEST_GAP_SECONDS - (time.time() - self._last_request)
        if gap > 0:
            time.sleep(gap)

    def _get_json(self, url: str, *, attempts: int = 3) -> dict | None:
        import requests
        for attempt in range(1, attempts + 1):
            self._throttle()
            try:
                r = self.session.get(url, timeout=20)
                self._last_request = time.time()
                if r.status_code == 404:
                    return None
                if r.status_code in (429, 503):
                    wait = min(30, 2 ** attempt)
                    log.warning("rebrickable rate-limited (%s) on %s; waiting %ss",
                                r.status_code, url, wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException as exc:
                if attempt == attempts:
                    raise ImageError(
                        f"{url} failed after {attempts} attempts: {exc}") from exc
                time.sleep(2 ** attempt)
        raise ImageError(f"exhausted attempts for {url}")

    def lookup_image_url(self, set_number: str) -> str | None:
        """Rebrickable set numbers carry a variant suffix. `-1` is the primary
        release and is what every set this site tracks turned out to use when
        this was tested against the real API; a set with no `-1` entry
        returns None rather than guessing at another suffix. If that ever
        turns out to be wrong for some set, the fix is to try that set's real
        variant number, not to loop over guesses here.
        """
        data = self._get_json(API_URL.format(set_num=f"{set_number}-1"))
        if not data:
            return None
        return data.get("set_img_url") or None

    def _download_and_resize(self, url: str, dest: Path) -> None:
        from io import BytesIO
        from PIL import Image

        self._throttle()
        r = self.session.get(url, timeout=30)
        self._last_request = time.time()
        r.raise_for_status()

        img = Image.open(BytesIO(r.content))
        img = img.convert("RGB")
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)

    def fetch_all(self, set_numbers: Iterable[str], out_dir: Path) -> dict[str, str]:
        """Downloads any set image not already on disk.

        Returns {set_number: path relative to out_dir's parent}, suitable for
        writing straight into a manifest. A set with no image is logged and
        skipped -- never fabricated, and never treated as a reason to fail
        the rest of the run (the same isolated-failure shape every other
        source in this project already follows).
        """
        manifest: dict[str, str] = {}
        misses: list[str] = []
        wanted = list(set_numbers)
        for setnum in wanted:
            dest = out_dir / f"{setnum}.jpg"
            if dest.exists():
                manifest[setnum] = str(dest.relative_to(out_dir.parent))
                continue
            try:
                img_url = self.lookup_image_url(setnum)
                if not img_url:
                    misses.append(setnum)
                    continue
                self._download_and_resize(img_url, dest)
                manifest[setnum] = str(dest.relative_to(out_dir.parent))
            except ImageError as exc:
                misses.append(setnum)
                log.warning("rebrickable: %s", exc)

        log.info("rebrickable images: %d available (fetched or cached), "
                  "%d missing, of %d sets", len(manifest), len(misses), len(wanted))
        if misses:
            shown = ", ".join(misses[:20]) + ("…" if len(misses) > 20 else "")
            log.info("no image found for: %s", shown)
        return manifest
