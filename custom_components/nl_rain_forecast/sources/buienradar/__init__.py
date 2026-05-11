"""Buienradar source: per-5-minute rain nowcast for the Netherlands."""

from __future__ import annotations

from .._base import Source
from .client import BuienradarClient
from .const import ATTRIBUTION, DISPLAY_NAME, ENTITY_KEY, ID
from .errors import BuienradarAPIError
from .parser import parse_buienradar

SOURCE = Source(
    id=ID,
    display_name=DISPLAY_NAME,
    attribution=ATTRIBUTION,
    entity_key=ENTITY_KEY,
    client_factory=BuienradarClient,
)

__all__ = [
    "SOURCE",
    "BuienradarAPIError",
    "BuienradarClient",
    "parse_buienradar",
]
