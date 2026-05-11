"""Buienalarm source constants."""

from __future__ import annotations

from typing import Final

ID: Final = "buienalarm"
DISPLAY_NAME: Final = "Buienalarm"
ATTRIBUTION: Final = "Data provided by Buienalarm"
ENTITY_KEY: Final = "rain_forecast_buienalarm"

URL: Final = "https://cdn-secure.buienalarm.nl/api/3.4/forecast.php"

DEFAULT_DELTA_SECONDS: Final = 300
