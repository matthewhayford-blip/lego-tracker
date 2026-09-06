"""The one interface every price source implements.

Adding a source — a scraped page today, an Awin or Rakuten product feed in
phase 2 — means writing one class with one `fetch` method. Nothing downstream
(normalise, model, templates, build) knows or cares where a quote came from.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Protocol

log = logging.getLogger(__name__)

USER_AGENT = (
    "BrickExitBot/0.1 (+https://brickexit.example/about-our-bot) "
    "UK LEGO retirement tracker; contact: hello@brickexit.example"
)
REQUEST_GAP_SECONDS = 1.5   # deliberate politeness; do not lower


@dataclass(frozen=True)
class PriceQuote:
    """One retailer's price for one set at one moment."""
    set_number: str
    retailer: str
    price_gbp: Decimal
    in_stock: bool
    url: str
    source: str                      # which module produced it — for CI triage
    seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rrp_gbp: Decimal | None = None

    def to_json(self) -> dict:
        d = asdict(self)
        d["price_gbp"] = float(self.price_gbp)
        d["rrp_gbp"] = float(self.rrp_gbp) if self.rrp_gbp is not None else None
        d["seen_at"] = self.seen_at.isoformat()
        return d


class SourceError(RuntimeError):
    """Raised when a source cannot produce quotes. Message goes to CI logs."""


class PriceSource(Protocol):
    name: str
    def fetch(self, set_numbers: Iterable[str]) -> list[PriceQuote]: ...


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def parse_price(raw) -> Decimal | None:
    """'£42.99', '42.99', 4299 (pence) -> Decimal. None if unparseable."""
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw))
    s = str(raw).strip().replace("\xa0", " ")
    for junk in ("£", "GBP", ",", " "):
        s = s.replace(junk, "")
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def extract_json_ld(html: str) -> list[dict]:
    """Pull every JSON-LD block out of a page.

    Prefer this over CSS selectors wherever a site offers it. JSON-LD exists so
    machines can read the page, so retailers keep it stable and correct across
    redesigns — which is exactly the breakage a selector-based scraper suffers.
    """
    from bs4 import BeautifulSoup

    out: list[dict] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out.extend(data if isinstance(data, list) else [data])
    # @graph wrappers are common
    flat: list[dict] = []
    for node in out:
        if isinstance(node, dict) and "@graph" in node:
            flat.extend(n for n in node["@graph"] if isinstance(n, dict))
        elif isinstance(node, dict):
            flat.append(node)
    return flat


def offers_from_product(node: dict) -> tuple[Decimal | None, bool]:
    """(price, in_stock) from a schema.org Product node."""
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if not isinstance(offers, dict):
        return None, False
    price = parse_price(offers.get("price") or offers.get("lowPrice"))
    avail = str(offers.get("availability", "")).lower()
    in_stock = "outofstock" not in avail and "soldout" not in avail
    return price, in_stock


class HttpSource:
    """Base class giving polite, retrying, logged HTTP with a real UA."""
    name = "http"
    timeout = 20

    def __init__(self, session=None):
        import requests
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-GB,en;q=0.9",
        })
        self._last_request = 0.0

    def get(self, url: str, *, attempts: int = 3) -> str:
        import requests
        for attempt in range(1, attempts + 1):
            gap = REQUEST_GAP_SECONDS - (time.time() - self._last_request)
            if gap > 0:
                time.sleep(gap)
            try:
                r = self.session.get(url, timeout=self.timeout)
                self._last_request = time.time()
                if r.status_code == 404:
                    raise SourceError(f"404 {url}")
                if r.status_code in (429, 503):
                    wait = min(30, 2 ** attempt)
                    log.warning("%s rate-limited (%s) on %s; waiting %ss",
                                self.name, r.status_code, url, wait)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.text
            except requests.RequestException as exc:
                if attempt == attempts:
                    raise SourceError(f"{self.name}: {url} failed after "
                                      f"{attempts} attempts: {exc}") from exc
                time.sleep(2 ** attempt)
        raise SourceError(f"{self.name}: exhausted attempts for {url}")
