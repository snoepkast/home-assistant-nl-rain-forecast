"""Coordinator tests — verifying partial-result and full-failure semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nl_rain_forecast.coordinator import NLRainForecastCoordinator
from custom_components.nl_rain_forecast.models import Forecast
from custom_components.nl_rain_forecast.sources import BUIENALARM, BUIENRADAR
from custom_components.nl_rain_forecast.sources.buienalarm import BuienalarmAPIError
from custom_components.nl_rain_forecast.sources.buienradar import BuienradarAPIError


def _forecast(source_id: str) -> Forecast:
    return Forecast(source=source_id, fetched_at=datetime(2026, 5, 8, 14, tzinfo=UTC), slots=())


def _make_coordinator(hass, *, buienradar_side, buienalarm_side):
    def _client(side):
        client = MagicMock()
        client.async_get_forecast = AsyncMock(side_effect=side)
        return client

    clients = {
        BUIENRADAR: _client(buienradar_side),
        BUIENALARM: _client(buienalarm_side),
    }
    config_entry = MagicMock(entry_id="test_entry")

    return NLRainForecastCoordinator(
        hass,
        config_entry=config_entry,
        clients=clients,
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
    assert data.get("buienradar") is not None
    assert data.get("buienalarm") is not None
    assert data.errors == {"buienradar": None, "buienalarm": None}


async def test_buienradar_fails_buienalarm_succeeds(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=BuienradarAPIError("upstream down"),
        buienalarm_side=lambda *_: _forecast("buienalarm"),
    )
    data = await coord._async_update_data()
    assert data.get("buienradar") is None
    assert data.get("buienalarm") is not None
    assert data.errors["buienradar"] == "upstream down"
    assert data.errors["buienalarm"] is None


async def test_buienalarm_fails_buienradar_succeeds(hass):
    coord = _make_coordinator(
        hass,
        buienradar_side=lambda *_: _forecast("buienradar"),
        buienalarm_side=BuienalarmAPIError("503"),
    )
    data = await coord._async_update_data()
    assert data.get("buienradar") is not None
    assert data.get("buienalarm") is None
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
    assert data.get("buienradar") is None
    assert data.get("buienalarm") is not None
    assert data.errors["buienradar"].startswith("unexpected: RuntimeError")
