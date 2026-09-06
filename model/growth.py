"""Growth model for retiring LEGO sets.

Market-aware: every money-denominated assumption (RRP bands, selling fee,
postage) is read from a market dict defined in config.MARKETS. The appreciation
rates themselves are not market-specific -- the source study is a global
secondary-market finding -- but the costs of realising them very much are.


Calibration anchors
-------------------
Dobrynskaya & Kishilova, "LEGO - The Toy of Smart Investors"
(Research in International Business and Finance, 2022): 2,322 retired sets,
1987-2015. ~11% nominal average annual return on the sealed secondary market,
sd 25-28%, Sharpe ~0.4, 90% of sets positive. Returns are U-shaped in set size:
small sets (<340 pieces) ~22%, mid-size (660-1,200) ~7%, very large (3,000+)
~18.5%. eBay-style transaction costs cut ~9pp off gross in their sample.

Theme tiering is a market-consensus overlay on that 11% base, not a fitted
regression. Every rate here is an assumption, exposed in the UI so it can be
argued with.
"""

# Expected annual appreciation of a SEALED set's market value, measured from
# UK RRP, applied only after the post-retirement flat period.
BASE_RATE = {
    "Star Wars":        0.115,
    "Ideas":            0.130,
    "Icons":            0.110,
    "Architecture":     0.090,
    "Botanicals":       0.070,
    "Harry Potter":     0.105,
    "Marvel":           0.075,
    "DC":               0.075,
    "Technic":          0.080,
    "Art":              0.085,
    "Ninjago":          0.055,
    "DREAMZzz":         0.040,
    "Super Mario":      0.070,
    "Animal Crossing":  0.070,
    "Fortnite":         0.055,
    "Horizon":          0.055,
    "Sonic":            0.050,
    "Creator":          0.070,
    "Wicked":           0.065,
    "Wednesday":        0.065,
    "One Piece":        0.075,
    "Speed Champions":  0.070,
    "Minifigures":      0.120,
    "Disney":           0.080,
    "Jurassic World":   0.070,
    "City":             0.050,
    "Friends":          0.050,
    "Bluey":            0.035,
    "Nike":             0.045,
    "Editions":         0.045,
    "BrickHeadz":       0.060,
    "Minecraft":        0.070,
    "Seasonal":         0.090,
    "Classic":          0.040,
    "Exclusive":        0.085,
}

# RRP band stands in for piece count (which we do not hold for every set).
# Shaped to the paper's U-curve: cheap sets and flagships beat the middle.
#
# Thresholds and currency symbol come from the market, because "a small set"
# is a different number of pounds than it is of dollars. Passing the market in
# rather than converting keeps each market's bands independently tunable.
def rrp_band_adj(rrp, mkt):
    lo, mid, high, flag = mkt["rrp_bands"]
    sym = mkt["symbol"]
    if rrp < lo:   return 0.010, f"small set (<{sym}{lo:g}) — U-curve upside"
    if rrp < mid:  return 0.000, f"{sym}{lo:g}-{mid:g} band — neutral"
    if rrp < high: return -0.005, f"{sym}{mid:g}-{high:g} band — crowded middle"
    if rrp < flag: return 0.010, f"{sym}{high:g}-{flag:g} band — collector sweet spot"
    return 0.020, f"{sym}{flag:g}+ flagship — scarcity at retirement"

FLAG_ADJ = {
    "d2c":  (0.020, "LEGO-exclusive — no third-party clearance flood"),
    "lic":  (0.010, "evergreen licence — demand outlives the wave"),
    "sat":  (-0.015, "mass-retail saturated — heavy discounting, high supply"),
    "icon": (0.020, "iconic one-off — unlikely to be re-released"),
    "new":  (-0.010, "unproven licence — no retirement track record"),
}

LOW_CONFIDENCE_THEMES = {"Fortnite", "Horizon", "Wicked", "Wednesday",
                         "One Piece", "Nike", "Editions", "Bluey"}
HIGH_CONFIDENCE_THEMES = {"Star Wars", "Ideas", "Icons", "Harry Potter",
                          "Architecture", "Technic", "Creator", "City",
                          "Friends", "Minecraft", "Disney", "Marvel"}

# Months after retirement during which sealed value typically sits flat while
# remaining retail stock clears. Appreciation is only modelled after this.
FLAT_MONTHS = 9

def selling_fee(mkt):
    """Marketplace + payment processing on a secondary-market sale."""
    return mkt["selling_fee"]


def shipping_cost(rrp, mkt):
    floor, cap, rate = mkt["shipping"]
    return round(min(cap, max(floor, rrp * rate)), 2)


def growth_rate(theme, rrp, flags, mkt):
    base = BASE_RATE.get(theme, 0.070)
    parts = [{"label": f"{theme} base rate", "value": base}]
    band, band_label = rrp_band_adj(rrp, mkt)
    parts.append({"label": band_label, "value": band})
    total = base + band
    for f in flags:
        if f in FLAG_ADJ:
            adj, label = FLAG_ADJ[f]
            parts.append({"label": label, "value": adj})
            total += adj
    total = max(0.015, min(0.20, total))
    return total, parts


def confidence(theme, flags):
    if "new" in flags or theme in LOW_CONFIDENCE_THEMES:
        return "low"
    if theme in HIGH_CONFIDENCE_THEMES or "d2c" in flags:
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Value path. Kept here so the site build and any future API agree exactly.
# ---------------------------------------------------------------------------
from datetime import date as _date

def years_between(a, b):
    return (b - a).days / 365.25


def projected_value(rrp, growth, retire_date, at_date, today=None):
    """Sealed market value at `at_date`.

    Holds at RRP until retirement, stays flat for FLAT_MONTHS while remaining
    retail stock clears, then compounds at `growth`.
    """
    flat_years = FLAT_MONTHS / 12
    start = retire_date and years_between(retire_date, at_date) - flat_years
    if start is None or start <= 0:
        return rrp
    return rrp * (1 + growth) ** start


def net_proceeds(gross, rrp, mkt):
    return gross * (1 - selling_fee(mkt)) - shipping_cost(rrp, mkt)


def cagr(net, buy_price, years):
    if buy_price <= 0 or years <= 0 or net <= 0:
        return None
    return (net / buy_price) ** (1 / years) - 1


def grade(c):
    if c is None:      return "F"
    if c >= 0.12:      return "A"
    if c >= 0.08:      return "B"
    if c >= 0.04:      return "C"
    if c >= 0:         return "D"
    return "F"
