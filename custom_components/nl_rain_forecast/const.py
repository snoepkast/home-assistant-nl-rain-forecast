"""Constants for the NL Rain Forecast integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "nl_rain_forecast"
LOGGER: Final = logging.getLogger(__package__)

# Config keys
CONF_LOCATION_NAME: Final = "location_name"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Defaults / bounds
DEFAULT_UPDATE_INTERVAL_MINUTES: Final = 5
MIN_UPDATE_INTERVAL_MINUTES: Final = 5
MAX_UPDATE_INTERVAL_MINUTES: Final = 60

# Netherlands bounding box (rough — covers mainland + Wadden + Zeeland).
NL_LAT_MIN: Final = 50.5
NL_LAT_MAX: Final = 53.7
NL_LON_MIN: Final = 3.2
NL_LON_MAX: Final = 7.3

# Source identifiers (also used as suffix in entity unique_ids).
SOURCE_BUIENRADAR: Final = "buienradar"
SOURCE_BUIENALARM: Final = "buienalarm"

ATTRIBUTION_BUIENRADAR: Final = "Data provided by Buienradar"
ATTRIBUTION_BUIENALARM: Final = "Data provided by Buienalarm"

# HTTP
HTTP_TIMEOUT_SECONDS: Final = 10
USER_AGENT: Final = "home-assistant-nl-rain-forecast"
