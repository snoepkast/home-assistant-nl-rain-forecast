"""Coordinator tests — verifying partial-result and full-failure semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nl_rain_forecast.coordinator import NLRainForecastCoordinator
from custom_components.nl_rain_forecast.models import (
    BuienalarmAPIError,
    BuienradarAPIError,
    Forecast,
)


def _forecast(source: str) -> Forecast:
    return Forecast(source=source, fetched_at=datetime(2026, 5, 8, 14, tzinfo=UTC), slots=())


def _make_coordinator(hass, *, buienradar_side, buienalarm_side):
    radar = MagicMock()
    alarm = MagicMock()
    radar.async_get_forecast = AsyncMock(side_effect=buienradar_side)
    alarm.async_get_forecast = AsyncMock(side_effect=buienalarm_side)

    config_entry = MagicMock(entry_id="test_entry")

    return NLRainForecastCoordinator(
        hass,
        config_entry=config_entry,
        buienradar=radar,
        buienalarm=alarm,
        latitude=52.0,
        longitude=5.0,
        update_interval=timedelta(minutes=5),
    )


async def test_both_succeed(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=lambda *_: _forecast("buienradar"),
        buienalarm_side=lambda *_: _forecast("buienalarm"),
    )
    data = await coord._async_update_data()
    assert data.buienradar is not None
    assert data.buienalarm is not None
    assert data.errors == {"buienradar": None, "buienalarm": None}


async def test_buienradar_fails_buienalarm_succeeds(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=BuienradarAPIError("upstream down"),
        buienalarm_side=lambda *_: _forecast("buienalarm"),
    )
    data = await coord._async_update_data()
    assert data.buienradar is None
    assert data.buienalarm is not None
    assert data.errors["buienradar"] == "upstream down"
    assert data.errors["buienalarm"] is None


async def test_buienalarm_fails_buienradar_succeeds(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=lambda *_: _forecast("buienradar"),
        buienalarm_side=BuienalarmAPIError("503"),
    )
    data = await coord._async_update_data()
    assert data.buienradar is not None
    assert data.buienalarm is None
    assert data.errors["buienalarm"] == "503"


async def test_both_fail_raises_update_failed(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=BuienradarAPIError("a"),
        buienalarm_side=BuienalarmAPIError("b"),
    )
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_unexpected_exception_treated_as_failure(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=RuntimeError("totally unexpected"),
        buienalarm_side=lambda *_: _forecast("buienalarm"),
    )
    data = await coord._async_update_data()
    assert data.buienradar is None
    assert data.buienalarm is not None
    assert data.errors["buienradar"].startswith("unexpected: RuntimeError")
