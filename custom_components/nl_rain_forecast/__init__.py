"""
NL Rain Forecast integration.

Custom integration that exposes Dutch per-5-minute rain nowcast data
(Buienradar + Buienalarm) as Home Assistant sensors.

https://github.com/snoepkast/home-assistant-nl-rain-forecast
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BuienalarmClient, BuienradarClient
from .const import (
    CONF_LOCATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    LOGGER,
)
from .coordinator import NLRainForecastCoordinator
from .data import NLRainForecastRuntimeData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import NLRainForecastConfigEntry

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NLRainForecastConfigEntry,
) -> bool:
    """Set up NL Rain Forecast from a config entry."""
    location_name = entry.data[CONF_LOCATION_NAME]
    latitude = float(entry.data[CONF_LATITUDE])
    longitude = float(entry.data[CONF_LONGITUDE])
    interval_minutes = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES),
    )

    session = async_get_clientsession(hass)
    integration_version = entry.data.get("integration_version", "0.1.0")

    buienradar = BuienradarClient(session)
    buienalarm = BuienalarmClient(session, version=integration_version)

    coordinator = NLRainForecastCoordinator(
        hass,
        config_entry=entry,
        buienradar=buienradar,
        buienalarm=buienalarm,
        latitude=latitude,
        longitude=longitude,
        update_interval=timedelta(minutes=int(interval_minutes)),
    )

    entry.runtime_data = NLRainForecastRuntimeData(
        coordinator=coordinator,
        buienradar=buienradar,
        buienalarm=buienalarm,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
    )

    LOGGER.info(
        "Setting up NL Rain Forecast for %s (%.4f, %.4f), update every %s min",
        location_name,
        latitude,
        longitude,
        interval_minutes,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NLRainForecastConfigEntry,
) -> bool:
    """Tear down a config entry."""
    LOGGER.info("Unloading NL Rain Forecast entry %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    entry: NLRainForecastConfigEntry,
) -> None:
    """Reload on options change so the new update interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)
