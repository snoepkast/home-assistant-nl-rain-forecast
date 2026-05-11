"""
DataUpdateCoordinator for NL Rain Forecast.

Fetches both Buienradar and Buienalarm in parallel. A failure of one
source does not prevent the other from succeeding — sensors for the
failed source go unavailable while sensors for the surviving source
keep updating.

Only when *both* sources fail is ``UpdateFailed`` raised, which makes
Home Assistant surface the integration as unavailable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SOURCE_BUIENALARM, SOURCE_BUIENRADAR
from .models import Forecast, RainForecastError

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import BuienalarmClient, BuienradarClient


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    """Result of one coordinator refresh."""

    buienradar: Forecast | None
    buienalarm: Forecast | None
    errors: dict[str, str | None]

    def get(self, source: str) -> Forecast | None:
        """Return the Forecast for ``source`` or None if unavailable."""
        if source == SOURCE_BUIENRADAR:
            return self.buienradar
        if source == SOURCE_BUIENALARM:
            return self.buienalarm
        return None


class NLRainForecastCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator that polls both rain APIs in parallel."""

    config_entry: ConfigEntry

    def __init__(  # noqa: PLR0913 — clients + coordinates + interval are all needed
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        buienradar: BuienradarClient,
        buienalarm: BuienalarmClient,
        latitude: float,
        longitude: float,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self._buienradar = buienradar
        self._buienalarm = buienalarm
        self._latitude = latitude
        self._longitude = longitude

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch both sources concurrently and assemble a CoordinatorData."""
        results = await asyncio.gather(
            self._buienradar.async_get_forecast(self._latitude, self._longitude),
            self._buienalarm.async_get_forecast(self._latitude, self._longitude),
            return_exceptions=True,
        )

        buienradar_result = self._unwrap(results[0], SOURCE_BUIENRADAR)
        buienalarm_result = self._unwrap(results[1], SOURCE_BUIENALARM)

        data = CoordinatorData(
            buienradar=buienradar_result[0],
            buienalarm=buienalarm_result[0],
            errors={
                SOURCE_BUIENRADAR: buienradar_result[1],
                SOURCE_BUIENALARM: buienalarm_result[1],
            },
        )

        if data.buienradar is None and data.buienalarm is None:
            msg = (
                "Both Buienradar and Buienalarm failed: "
                f"buienradar={data.errors[SOURCE_BUIENRADAR]}, "
                f"buienalarm={data.errors[SOURCE_BUIENALARM]}"
            )
            raise UpdateFailed(msg)

        return data

    @staticmethod
    def _unwrap(
        result: Forecast | BaseException,
        source: str,
    ) -> tuple[Forecast | None, str | None]:
        """Convert a gather result into ``(forecast, error_message)``."""
        if isinstance(result, Forecast):
            return result, None
        if isinstance(result, RainForecastError):
            LOGGER.warning("%s update failed: %s", source, result)
            return None, str(result)
        # Truly unexpected: log loud, surface the type so we don't silently swallow.
        LOGGER.exception("%s update raised an unexpected error", source, exc_info=result)
        return None, f"unexpected: {type(result).__name__}: {result}"
