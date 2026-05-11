"""
Generic source abstractions.

A "source" is one upstream nowcast provider (Buienradar, Buienalarm, …).
Each source ships as a subpackage under ``sources/`` and exports a
module-level :class:`Source` instance describing it.

The coordinator, sensor platform, and config flow consume the
:data:`SOURCES` tuple from :mod:`.` and treat each entry uniformly —
they never reference a source by hard-coded name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    import aiohttp

    from ..models import Forecast


class SourceClient(Protocol):
    """The minimal interface every source's HTTP client must implement."""

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""


@dataclass(frozen=True, slots=True)
class Source:
    """Static description of one rain-nowcast source."""

    id: str
    """Stable identifier; used in entity unique_ids and translation keys."""

    display_name: str
    """Human-readable name (e.g. ``"Buienradar"``)."""

    attribution: str
    """Attribution string surfaced on each sensor."""

    entity_key: str
    """Sensor key + translation key (e.g. ``"rain_forecast_buienradar"``)."""

    client_factory: Callable[[aiohttp.ClientSession], SourceClient]
    """Callable returning a fresh client bound to the given aiohttp session."""
