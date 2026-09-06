"""Single source of truth for branding, site identity and markets.

Renaming the project is a change to this file and nothing else.

Markets
-------
The site is UK-first and should stay that way until the UK ranks -- see the
handover. But every page lives under a market prefix (`/uk/...`) from day one,
because adding that prefix *after* URLs are indexed costs a site-wide 301 and
a ranking dip. Adding a second market is now a new entry in MARKETS plus a
price source that returns quotes in that currency; it is not a migration.

Nothing outside this file should hardcode a currency, a fee or a locale.
"""
from datetime import date

BRAND        = "Retired & Rare"
TAGLINE      = "LEGO retirement tracker"
DOMAIN       = "retiredandrare.com"
BASE_URL     = f"https://{DOMAIN}"

# While True every page emits <meta name="robots" content="noindex">.
# Flip to False only when the domain is final -- an indexed URL is expensive to move.
NOINDEX      = True

# Affiliate disclosure is required by ASA/CAP (and the FTC in the US) once
# links are monetised.
AFFILIATE_ACTIVE = False

DATA_DIR     = "data"
OUT_DIR      = "public"
BUILD_DATE   = date.today()

# ---------------------------------------------------------------------------
# Who runs this
# ---------------------------------------------------------------------------
# Affiliate networks and UK GDPR both want a named, contactable human. An
# anonymous site is a common rejection reason for solo affiliate applications.
# These are the only two facts the site cannot generate for itself.
#
# TODO before applying to Rakuten/Awin: set both. `build.py` refuses to render
# the trust pages while either still starts with "TODO", so an unfinished
# About page cannot ship by accident.
OWNER_NAME    = "Matt"
CONTACT_EMAIL = "hello@retiredandrare.com"

# Sole trader is the assumed structure -- the UK £1,000 trading allowance
# covers early affiliate revenue. If this becomes a limited company, the
# company number has to appear on the site.
BUSINESS_TYPE = "sole trader"


# ---------------------------------------------------------------------------
# Markets
# ---------------------------------------------------------------------------
# Each market is a self-contained set of assumptions. To add one: add an entry,
# add a price source that emits quotes with that currency, and provide RRPs in
# `data/sets.json` under `rrp.<market>`. Nothing else needs to change.
#
# rrp_bands: the U-curve from the source paper is about set *size*, which we
#   proxy with price. The thresholds are therefore local-currency equivalents
#   of the same real sets, not a converted number -- they need setting per
#   market by looking at what a "small set" actually costs there.
# selling_fee: marketplace + payment processing on a secondary-market sale.
# shipping: (floor, cap, rate) -- postage estimated as rrp * rate, clamped.

MARKETS = {
    "uk": {
        "code":         "uk",
        "name":         "United Kingdom",
        "adjective":    "UK",
        "locale":       "en-GB",
        "hreflang":     "en-GB",
        "currency":     "GBP",
        "symbol":       "\u00a3",
        "rrp_bands":    (20, 50, 120, 300),
        "selling_fee":  0.14,      # eBay UK final value fee + payment processing
        "shipping":     (3.60, 16.00, 0.045),
        "enabled":      True,
    },
    # Not enabled. Present so the shape is testable and the build is proven
    # market-agnostic rather than merely claimed to be. Enabling it needs a
    # US price source and per-set USD RRPs first.
    "us": {
        "code":         "us",
        "name":         "United States",
        "adjective":    "US",
        "locale":       "en-US",
        "hreflang":     "en-US",
        "currency":     "USD",
        "symbol":       "$",
        "rrp_bands":    (25, 60, 150, 380),
        "selling_fee":  0.15,      # eBay US final value fee + payment processing
        "shipping":     (5.00, 20.00, 0.050),
        "enabled":      False,
    },
}

DEFAULT_MARKET = "uk"


def enabled_markets() -> list[dict]:
    """Markets the build should actually generate, default first."""
    ms = [m for m in MARKETS.values() if m["enabled"]]
    ms.sort(key=lambda m: (m["code"] != DEFAULT_MARKET, m["code"]))
    return ms


def market(code: str) -> dict:
    return MARKETS[code]


def money(amount, mkt, dp: int = 2) -> str:
    """Format an amount in a market's currency. The only place a symbol is placed."""
    return f"{mkt['symbol']}{amount:,.{dp}f}"
