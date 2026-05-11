"""Open-Meteo source: 15-min rain forecast linearly interpolated to 5-min cadence."""

from __future__ import annotations

from .._base import Source
from .client import OpenMeteoClient
from .const import ATTRIBUTION, DISPLAY_NAME, ENTITY_KEY, ID
from .errors import OpenMeteoAPIError
from .parser import parse_open_meteo

SOURCE = Source(
    id=ID,
    display_name=DISPLAY_NAME,
    attribution=ATTRIBUTION,
    entity_key=ENTITY_KEY,
    client_factory=OpenMeteoClient,
)

__all__ = [
    "SOURCE",
    "OpenMeteoAPIError",
    "OpenMeteoClient",
    "parse_open_meteo",
]
