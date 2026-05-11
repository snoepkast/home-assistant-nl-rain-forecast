"""Async HTTP client for the Open-Meteo ``/v1/forecast`` endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp

from ...const import HTTP_TIMEOUT_SECONDS, USER_AGENT
from ...models import APIParseError, APIResponseError, APITimeoutError
from .const import UPSTREAM_SLOTS_REQUESTED, URL
from .errors import OpenMeteoAPIError
from .parser import parse_open_meteo

if TYPE_CHECKING:
    from ...models import Forecast

_LOGGER = logging.getLogger(__name__)


class OpenMeteoClient:
    """HTTP wrapper around the Open-Meteo /v1/forecast endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "minutely_15": "precipitation",
            "forecast_minutely_15": str(UPSTREAM_SLOTS_REQUESTED),
            "timezone": "GMT",
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            async with asyncio.timeout(HTTP_TIMEOUT_SECONDS):
                response = await self._session.get(URL, params=params, headers=headers)
                if response.status >= 400:  # noqa: PLR2004
                    body_preview = (await response.text())[:200]
                    msg = f"Open-Meteo HTTP {response.status}: {body_preview!r}"
                    raise APIResponseError(msg)
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as exc:
                    body_preview = (await response.text())[:200]
                    msg = f"Open-Meteo returned non-JSON body: {body_preview!r}"
                    raise APIParseError(msg) from exc
        except TimeoutError as exc:
            msg = f"Open-Meteo timed out after {HTTP_TIMEOUT_SECONDS}s"
            raise APITimeoutError(msg) from exc
        except aiohttp.ClientError as exc:
            msg = f"Open-Meteo transport error: {exc}"
            raise OpenMeteoAPIError(msg) from exc

        fetched_at = datetime.now(UTC)
        try:
            return parse_open_meteo(payload, fetched_at=fetched_at)
        except APIParseError as exc:
            _LOGGER.warning("Open-Meteo parse failed: %s", exc)
            raise OpenMeteoAPIError(str(exc)) from exc
