"""End-to-end sensor tests via the integration setup path."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nl_rain_forecast.const import (
    CONF_LOCATION_NAME,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from custom_components.nl_rain_forecast.models import Forecast, build_slots
from custom_components.nl_rain_forecast.sources.buienalarm import BuienalarmAPIError

from .test_buienradar_parser import _fetched_at as _radar_now


def _entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="52.0_5.0",
        data={
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: 52.0,
            CONF_LONGITUDE: 5.0,
        },
        options={CONF_UPDATE_INTERVAL: 5},
    )
    entry.add_to_hass(hass)
    return entry


def _radar_forecast() -> Forecast:
    base = _radar_now()
    return Forecast(
        source="buienradar",
        fetched_at=base,
        slots=build_slots(base, [0.0, 0.5, 1.0, 0.0, 0.0]),
    )


def _alarm_forecast() -> Forecast:
    base = _radar_now()
    return Forecast(
        source="buienalarm",
        fetched_at=base,
        slots=build_slots(base, [0.0, 0.0, 0.0]),
    )


async def test_sensors_created_with_state_and_attributes(hass):
    entry = _entry(hass)

    with (
        patch(
            "custom_components.nl_rain_forecast.sources.buienradar.BuienradarClient.async_get_forecast",
            new=AsyncMock(return_value=_radar_forecast()),
        ),
        patch(
            "custom_components.nl_rain_forecast.sources.buienalarm.BuienalarmClient.async_get_forecast",
            new=AsyncMock(return_value=_alarm_forecast()),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    radar_state = hass.states.get("sensor.home_rain_forecast_buienradar")
    alarm_state = hass.states.get("sensor.home_rain_forecast_buienalarm")
    assert radar_state is not None
    assert alarm_state is not None

    # First slot is 0.0 mm/h.
    assert float(radar_state.state) == 0.0
    # Forecast attribute carries all 5 slots.
    assert len(radar_state.attributes["forecast"]) == 5
    assert radar_state.attributes["peak_intensity"] == 1.0
    assert radar_state.attributes["next_rain_in_minutes"] == 5
    assert radar_state.attributes["source"] == "buienradar"
    assert radar_state.attributes["unit_of_measurement"] == "mm/h"


async def test_partial_failure_keeps_surviving_source_available(hass):
    entry = _entry(hass)

    with (
        patch(
            "custom_components.nl_rain_forecast.sources.buienradar.BuienradarClient.async_get_forecast",
            new=AsyncMock(return_value=_radar_forecast()),
        ),
        patch(
            "custom_components.nl_rain_forecast.sources.buienalarm.BuienalarmClient.async_get_forecast",
            new=AsyncMock(side_effect=BuienalarmAPIError("down")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    radar_state = hass.states.get("sensor.home_rain_forecast_buienradar")
    alarm_state = hass.states.get("sensor.home_rain_forecast_buienalarm")
    # Buienradar still serving data
    assert radar_state.state not in ("unavailable", "unknown")
    # Buienalarm reports unavailable
    assert alarm_state.state == "unavailable"
