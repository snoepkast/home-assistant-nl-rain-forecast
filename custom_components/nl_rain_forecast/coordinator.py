"""
DataUpdateCoordinator for NL Rain Forecast.

Fetches every configured :class:`Source` in parallel. A failure of one
source does not prevent the other(s) from succeeding — sensors for the
failed source go unavailable while sensors for the surviving sources
keep updating.

Only when *every* source fails is ``UpdateFailed`` raised, which makes
Home Assistant surface the integration as unavailable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER
from .models import Forecast, RainForecastError

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .sources import Source, SourceClient


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    """
    Result of one coordinator refresh.

    ``forecasts`` and ``errors`` are keyed by :attr:`Source.id`; missing
    keys mean the corresponding source has never produced a result.
    """

    forecasts: dict[str, Forecast | None]
    errors: dict[str, str | None]

    def get(self, source_id: str) -> Forecast | None:
        """Return the Forecast for ``source_id`` or ``None`` if unavailable."""
        return self.forecasts.get(source_id)


class NLRainForecastCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinator that polls every configured source in parallel."""

    config_entry: ConfigEntry

    def __init__(  # noqa: PLR0913 — clients + coordinates + interval are all needed
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        clients: dict[Source, SourceClient],
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
        self._clients = clients
        self._latitude = latitude
        self._longitude = longitude

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch every source concurrently and assemble a CoordinatorData."""
        sources = list(self._clients)
        results = await asyncio.gather(
            *(
                self._clients[source].async_get_forecast(self._latitude, self._longitude)
                for source in sources
            ),
            return_exceptions=True,
        )

        forecasts: dict[str, Forecast | None] = {}
        errors: dict[str, str | None] = {}
        for source, result in zip(sources, results, strict=True):
            forecast, error = self._unwrap(result, source.id)
            forecasts[source.id] = forecast
            errors[source.id] = error

        data = CoordinatorData(forecasts=forecasts, errors=errors)

        if all(forecast is None for forecast in data.forecasts.values()):
            details = ", ".join(f"{sid}={err}" for sid, err in data.errors.items())
            msg = f"All sources failed: {details}"
            raise UpdateFailed(msg)

        return data

    @staticmethod
    def _unwrap(
        result: Forecast | BaseException,
        source_id: str,
    ) -> tuple[Forecast | None, str | None]:
        """Convert a gather result into ``(forecast, error_message)``."""
        if isinstance(result, Forecast):
            return result, None
        if isinstance(result, RainForecastError):
            LOGGER.warning("%s update failed: %s", source_id, result)
            return None, str(result)
        LOGGER.exception("%s update raised an unexpected error", source_id, exc_info=result)
        return None, f"unexpected: {type(result).__name__}: {result}"
