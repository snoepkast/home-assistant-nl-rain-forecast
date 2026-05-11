"""Runtime data shape for the NL Rain Forecast integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import NLRainForecastCoordinator
    from .sources import Source, SourceClient

    type NLRainForecastConfigEntry = ConfigEntry[NLRainForecastRuntimeData]


@dataclass(slots=True)
class NLRainForecastRuntimeData:
    """Lives on ``ConfigEntry.runtime_data`` for the lifetime of the entry."""

    coordinator: NLRainForecastCoordinator
    clients: dict[Source, SourceClient]
    location_name: str
    latitude: float
    longitude: float
