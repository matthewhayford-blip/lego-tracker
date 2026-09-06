"""Single source of truth for branding and site identity.

Renaming the project is a change to this file and nothing else.
"""
from datetime import date

BRAND        = "Brick Exit"
TAGLINE      = "UK LEGO retirement tracker"
DOMAIN       = "brickexit.example"        # TODO: set real domain before launch
BASE_URL     = f"https://{DOMAIN}"
LOCALE       = "en-GB"
CURRENCY     = "GBP"

# While True every page emits <meta name="robots" content="noindex">.
# Flip to False only when the domain is final — an indexed URL is expensive to move.
NOINDEX      = True

# Affiliate disclosure is required by ASA/CAP once links are monetised.
AFFILIATE_ACTIVE = False

DATA_DIR     = "data"
OUT_DIR      = "public"
BUILD_DATE   = date.today()
