"""Runtime data shape for the NL Rain Forecast integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .api import BuienalarmClient, BuienradarClient
    from .coordinator import NLRainForecastCoordinator

    type NLRainForecastConfigEntry = ConfigEntry[NLRainForecastRuntimeData]


@dataclass(slots=True)
class NLRainForecastRuntimeData:
    """Lives on ``ConfigEntry.runtime_data`` for the lifetime of the entry."""

    coordinator: NLRainForecastCoordinator
    buienradar: BuienradarClient
    buienalarm: BuienalarmClient
    location_name: str
    latitude: float
    longitude: float
