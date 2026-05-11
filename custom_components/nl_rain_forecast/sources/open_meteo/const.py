"""Open-Meteo source constants."""

from __future__ import annotations

from typing import Final

ID: Final = "open_meteo"
DISPLAY_NAME: Final = "Open-Meteo"
ATTRIBUTION: Final = "Data provided by Open-Meteo.com"
ENTITY_KEY: Final = "rain_forecast_open_meteo"

URL: Final = "https://api.open-meteo.com/v1/forecast"

# Upstream native cadence is 15 min; we request just enough slots to cover
# roughly the same 2h window the other sources offer, then linearly
# interpolate to 5-min cadence.
UPSTREAM_INTERVAL_MINUTES: Final = 15
TARGET_INTERVAL_MINUTES: Final = 5
UPSTREAM_SLOTS_REQUESTED: Final = 9  # 9 * 15min = 2h15m -> 25 fine slots after interp

# Open-Meteo returns precipitation as mm accumulated over the slot's interval.
# To convert to an mm/h intensity, multiply by (60 / UPSTREAM_INTERVAL_MINUTES).
MM_PER_INTERVAL_TO_MM_PER_HOUR: Final = 60 / UPSTREAM_INTERVAL_MINUTES
