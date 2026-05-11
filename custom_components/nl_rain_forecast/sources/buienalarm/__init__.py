"""Buienalarm source: per-5-minute rain forecast for the Netherlands."""

from __future__ import annotations

from .._base import Source
from .client import BuienalarmClient
from .const import ATTRIBUTION, DISPLAY_NAME, ENTITY_KEY, ID
from .errors import BuienalarmAPIError
from .parser import parse_buienalarm

SOURCE = Source(
    id=ID,
    display_name=DISPLAY_NAME,
    attribution=ATTRIBUTION,
    entity_key=ENTITY_KEY,
    client_factory=BuienalarmClient,
)

__all__ = [
    "SOURCE",
    "BuienalarmAPIError",
    "BuienalarmClient",
    "parse_buienalarm",
]
