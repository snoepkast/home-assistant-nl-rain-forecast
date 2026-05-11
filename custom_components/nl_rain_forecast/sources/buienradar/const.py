"""Buienradar source constants."""

from __future__ import annotations

from typing import Final
from zoneinfo import ZoneInfo

ID: Final = "buienradar"
DISPLAY_NAME: Final = "Buienradar"
ATTRIBUTION: Final = "Data provided by Buienradar"
ENTITY_KEY: Final = "rain_forecast_buienradar"

URL: Final = "https://gpsgadget.buienradar.nl/data/raintext"

# HH:MM in the upstream payload is local Dutch time.
TIMEZONE: Final = ZoneInfo("Europe/Amsterdam")

# Intensity → mm/h conversion: ``mm/h = 10 ** ((value - SHIFT) / DIVISOR)``.
INTENSITY_MAX: Final = 255
FORMULA_SHIFT: Final = 109
FORMULA_DIVISOR: Final = 32
