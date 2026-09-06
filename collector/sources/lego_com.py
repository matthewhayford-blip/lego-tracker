"""LEGO.com UK — official prices and LEGO's own retiring flags.

The most authoritative source we have: it is the manufacturer, it states RRP
and current price, and its "Retiring soon" badge is LEGO's own signal rather
than fan-media inference. Worth more than any aggregator for the sets it covers.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from .base import (HttpSource, PriceQuote, SourceError, extract_json_ld,
                   offers_from_product, parse_price)

log = logging.getLogger(__name__)

RETIRING_URL = "https://www.lego.com/en-gb/categories/retiring-soon"
PRODUCT_URL = "https://www.lego.com/en-gb/product/{slug}"
SET_RE = re.compile(r"(\d{4,7})")


class LegoComSource(HttpSource):
    name = "lego.com"
    retailer = "LEGO UK"
    market = "uk"          # this source reports en-gb pages only
    currency = "GBP"

    def fetch(self, set_numbers: Iterable[str]) -> list[PriceQuote]:
        wanted = {str(s) for s in set_numbers}
        quotes = self._fetch_retiring_category()
        found = {q.set_number for q in quotes}
        log.info("%s: %d quotes from category page, %d of them wanted",
                 self.name, len(quotes), len(found & wanted))
        return [q for q in quotes if q.set_number in wanted] if wanted else quotes

    # -- internals ---------------------------------------------------------

    def _fetch_retiring_category(self) -> list[PriceQuote]:
        html = self.get(RETIRING_URL)
        quotes = self._from_json_ld(html)
        if quotes:
            return quotes
        log.warning("%s: no JSON-LD on category page, falling back to HTML",
                    self.name)
        quotes = self._from_html(html)
        if not quotes:
            raise SourceError(
                f"{self.name}: extracted zero products from {RETIRING_URL}. "
                "Both JSON-LD and the HTML fallback found nothing — the page "
                "structure has changed. Check the saved fixture in CI artifacts."
            )
        return quotes

    def _from_json_ld(self, html: str) -> list[PriceQuote]:
        out = []
        for node in extract_json_ld(html):
            types = node.get("@type", "")
            types = types if isinstance(types, list) else [types]
            if "Product" not in types:
                continue
            setnum = self._set_number(node)
            price, in_stock = offers_from_product(node)
            if not setnum or price is None:
                continue
            out.append(PriceQuote(
                set_number=setnum,
                retailer=self.retailer,
                price=price,
                in_stock=in_stock,
                url=node.get("url") or RETIRING_URL,
                source=self.name,
                market=self.market, currency=self.currency,
            ))
        return out

    def _from_html(self, html: str) -> list[PriceQuote]:
        """Fallback: LEGO renders product tiles with data attributes."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        out = []
        for card in soup.select('[data-test="product-item"], article, li'):
            link = card.find("a", href=True)
            if not link:
                continue
            m = SET_RE.search(link["href"])
            if not m:
                continue
            price_el = card.select_one('[data-test*="price"], .product-price, span[class*="rice"]')
            price = parse_price(price_el.get_text() if price_el else None)
            if price is None:
                continue
            href = link["href"]
            out.append(PriceQuote(
                set_number=m.group(1),
                retailer=self.retailer,
                price=price,
                in_stock="out of stock" not in card.get_text().lower(),
                url=href if href.startswith("http") else f"https://www.lego.com{href}",
                source=self.name,
                market=self.market, currency=self.currency,
            ))
        return out

    @staticmethod
    def _set_number(node: dict) -> str | None:
        for key in ("sku", "mpn", "productID", "name", "url"):
            val = node.get(key)
            if not val:
                continue
            m = SET_RE.search(str(val))
            if m:
                return m.group(1)
        return None
