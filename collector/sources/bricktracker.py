"""BrickTracker — best price across several UK retailers, one page per set.

Second-hand data: it reports what Amazon, Argos, Smyths, John Lewis and Hamleys
charge rather than asking them directly. Broader than any single retailer and
requires no affiliate relationship, which is why it carries phase 1. Phase 2
replaces it with first-party product feeds.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from .base import (HttpSource, PriceQuote, SourceError, extract_json_ld,
                   offers_from_product, parse_price)

log = logging.getLogger(__name__)

SET_URL = "https://www.bricktracker.co.uk/set/{set_number}"
PRICE_RE = re.compile(r"£\s?(\d[\d,]*\.?\d{0,2})")


class BrickTrackerSource(HttpSource):
    name = "bricktracker"

    def fetch(self, set_numbers: Iterable[str]) -> list[PriceQuote]:
        out: list[PriceQuote] = []
        failures = 0
        wanted = list(set_numbers)
        for setnum in wanted:
            try:
                out.extend(self._fetch_one(str(setnum)))
            except SourceError as exc:
                failures += 1
                log.warning("%s: %s", self.name, exc)
                # A missing set is normal; wholesale failure is not.
                if failures > max(5, len(wanted) // 4):
                    raise SourceError(
                        f"{self.name}: {failures} failures in "
                        f"{len(wanted)} lookups — treating as source breakage "
                        "rather than missing sets."
                    ) from exc
        log.info("%s: %d quotes, %d lookups failed", self.name, len(out), failures)
        return out

    def _fetch_one(self, set_number: str) -> list[PriceQuote]:
        html = self.get(SET_URL.format(set_number=set_number))
        quotes = []
        for node in extract_json_ld(html):
            types = node.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if "Product" not in types:
                continue
            offers = node.get("offers")
            offers = offers if isinstance(offers, list) else [offers]
            for offer in filter(None, offers):
                price = parse_price(offer.get("price") or offer.get("lowPrice"))
                if price is None:
                    continue
                seller = offer.get("seller") or {}
                retailer = (seller.get("name") if isinstance(seller, dict) else None) \
                    or offer.get("offeredBy") or "Unknown retailer"
                avail = str(offer.get("availability", "")).lower()
                quotes.append(PriceQuote(
                    set_number=set_number,
                    retailer=str(retailer),
                    price_gbp=price,
                    in_stock="outofstock" not in avail,
                    url=offer.get("url") or SET_URL.format(set_number=set_number),
                    source=self.name,
                ))
        return quotes
