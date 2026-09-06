from .lego_com import LegoComSource
from .bricktracker import BrickTrackerSource

# Order matters only for tie-breaking identical prices; normalise.py picks the
# cheapest in-stock quote regardless. Add affiliate feed sources here in phase 2.
ALL_SOURCES = [LegoComSource, BrickTrackerSource]
