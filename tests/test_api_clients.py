"""HTTP-level tests for both API clients using aioresponses."""

from __future__ import annotations

import json
import re

import aiohttp
import pytest
from aioresponses import CallbackResult, aioresponses

from custom_components.nl_rain_forecast.models import (
    APIResponseError,
    RainForecastError,
)
from custom_components.nl_rain_forecast.sources.buienalarm import (
    BuienalarmAPIError,
    BuienalarmClient,
)
from custom_components.nl_rain_forecast.sources.buienalarm.const import URL as BUIENALARM_URL
from custom_components.nl_rain_forecast.sources.buienradar import (
    BuienradarAPIError,
    BuienradarClient,
)
from custom_components.nl_rain_forecast.sources.buienradar.const import URL as BUIENRADAR_URL
from custom_components.nl_rain_forecast.sources.open_meteo import (
    OpenMeteoAPIError,
    OpenMeteoClient,
)
from custom_components.nl_rain_forecast.sources.open_meteo.const import URL as OPEN_METEO_URL

from .conftest import load_fixture

BUIENRADAR_PATTERN = re.compile(re.escape(BUIENRADAR_URL) + r"\?.*")
BUIENALARM_PATTERN = re.compile(re.escape(BUIENALARM_URL) + r"\?.*")
OPEN_METEO_PATTERN = re.compile(re.escape(OPEN_METEO_URL) + r"\?.*")

LAT, LON = 52.3676, 4.9041


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


# --- Buienradar ----------------------------------------------------------


async def test_buienradar_happy_path(session):
    with aioresponses() as mocked:
        mocked.get(
            BUIENRADAR_PATTERN,
            status=200,
            body=load_fixture("buienradar_active.txt"),
        )
        client = BuienradarClient(session)
        forecast = await client.async_get_forecast(LAT, LON)
    assert len(forecast.slots) == 25
    assert forecast.peak_intensity == 10.0


async def test_buienradar_http_500_raises(session):
    with aioresponses() as mocked:
        mocked.get(BUIENRADAR_PATTERN, status=500, body="boom")
        client = BuienradarClient(session)
        with pytest.raises(APIResponseError):
            await client.async_get_forecast(LAT, LON)


async def test_buienradar_malformed_payload_raises(session):
    with aioresponses() as mocked:
        mocked.get(BUIENRADAR_PATTERN, status=200, body="totally not parseable")
        client = BuienradarClient(session)
        with pytest.raises(BuienradarAPIError):
            await client.async_get_forecast(LAT, LON)


async def test_buienradar_transport_error(session):
    with aioresponses() as mocked:
        mocked.get(BUIENRADAR_PATTERN, exception=aiohttp.ClientConnectionError("transport down"))
        client = BuienradarClient(session)
        with pytest.raises(BuienradarAPIError):
            await client.async_get_forecast(LAT, LON)


# --- Buienalarm ----------------------------------------------------------


async def test_buienalarm_happy_path(session):
    with aioresponses() as mocked:
        mocked.get(
            BUIENALARM_PATTERN,
            status=200,
            body=load_fixture("buienalarm_active.json"),
            content_type="application/json",
        )
        client = BuienalarmClient(session)
        forecast = await client.async_get_forecast(LAT, LON)
    assert len(forecast.slots) == 24
    assert forecast.peak_intensity == 5.0


async def test_buienalarm_http_500_raises(session):
    with aioresponses() as mocked:
        mocked.get(BUIENALARM_PATTERN, status=500, body="boom")
        client = BuienalarmClient(session)
        with pytest.raises(APIResponseError):
            await client.async_get_forecast(LAT, LON)


async def test_buienalarm_non_json_body_raises(session):
    with aioresponses() as mocked:
        mocked.get(
            BUIENALARM_PATTERN,
            status=200,
            body="<html>maintenance</html>",
            content_type="text/html",
        )
        client = BuienalarmClient(session)
        with pytest.raises(RainForecastError):
            await client.async_get_forecast(LAT, LON)


async def test_buienalarm_passes_user_agent(session):
    captured = {}

    def callback(_url, **kwargs):
        captured.update(kwargs.get("headers") or {})
        return CallbackResult(
            status=200,
            body=load_fixture("buienalarm_dry.json"),
            content_type="application/json",
        )

    with aioresponses() as mocked:
        mocked.get(BUIENALARM_PATTERN, callback=callback)
        client = BuienalarmClient(session)
        await client.async_get_forecast(LAT, LON)

    assert captured.get("User-Agent") == "home-assistant-nl-rain-forecast"


async def test_buienalarm_garbage_json_raises(session):
    with aioresponses() as mocked:
        mocked.get(
            BUIENALARM_PATTERN,
            status=200,
            payload={"unrelated": "object"},
            content_type="application/json",
        )
        client = BuienalarmClient(session)
        with pytest.raises(BuienalarmAPIError):
            await client.async_get_forecast(LAT, LON)


async def test_buienalarm_round_trips_real_fixture_payload(session):
    """Ensure round-tripping via JSON works (sanity for the fixture)."""
    payload = json.loads(load_fixture("buienalarm_active.json"))
    with aioresponses() as mocked:
        mocked.get(
            BUIENALARM_PATTERN,
            status=200,
            payload=payload,
            content_type="application/json",
        )
        client = BuienalarmClient(session)
        forecast = await client.async_get_forecast(LAT, LON)
    assert forecast.source == "buienalarm"


# --- Open-Meteo ----------------------------------------------------------


async def test_open_meteo_happy_path(session):
    with aioresponses() as mocked:
        mocked.get(
            OPEN_METEO_PATTERN,
            status=200,
            body=load_fixture("open_meteo_active.json"),
            content_type="application/json",
        )
        client = OpenMeteoClient(session)
        forecast = await client.async_get_forecast(LAT, LON)
    # 9 upstream slots * 15min -> 25 interpolated 5-min slots.
    assert len(forecast.slots) == 25
    assert forecast.peak_intensity == 2.0


async def test_open_meteo_http_500_raises(session):
    with aioresponses() as mocked:
        mocked.get(OPEN_METEO_PATTERN, status=500, body="boom")
        client = OpenMeteoClient(session)
        with pytest.raises(APIResponseError):
            await client.async_get_forecast(LAT, LON)


async def test_open_meteo_garbage_json_raises(session):
    with aioresponses() as mocked:
        mocked.get(
            OPEN_METEO_PATTERN,
            status=200,
            payload={"unrelated": "object"},
            content_type="application/json",
        )
        client = OpenMeteoClient(session)
        with pytest.raises(OpenMeteoAPIError):
            await client.async_get_forecast(LAT, LON)


async def test_open_meteo_transport_error(session):
    with aioresponses() as mocked:
        mocked.get(
            OPEN_METEO_PATTERN,
            exception=aiohttp.ClientConnectionError("transport down"),
        )
        client = OpenMeteoClient(session)
        with pytest.raises(OpenMeteoAPIError):
            await client.async_get_forecast(LAT, LON)


async def test_open_meteo_non_json_body_raises(session):
    with aioresponses() as mocked:
        mocked.get(
            OPEN_METEO_PATTERN,
            status=200,
            body="<html>maintenance</html>",
            content_type="text/html",
        )
        client = OpenMeteoClient(session)
        with pytest.raises(RainForecastError):
            await client.async_get_forecast(LAT, LON)
