"""Async HTTP client for the Buienalarm forecast endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import aiohttp

from ...const import HTTP_TIMEOUT_SECONDS, USER_AGENT
from ...models import APIParseError, APIResponseError, APITimeoutError
from .const import URL
from .errors import BuienalarmAPIError
from .parser import parse_buienalarm

if TYPE_CHECKING:
    from ...models import Forecast

_LOGGER = logging.getLogger(__name__)


class BuienalarmClient:
    """HTTP wrapper around the Buienalarm forecast endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""
        params = {
            "lat": f"{lat:.4f}",
            "lon": f"{lon:.4f}",
            "region": "nl",
            "unit": "mm/u",
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        try:
            async with asyncio.timeout(HTTP_TIMEOUT_SECONDS):
                response = await self._session.get(URL, params=params, headers=headers)
                if response.status >= 400:  # noqa: PLR2004
                    body_preview = (await response.text())[:200]
                    msg = f"Buienalarm HTTP {response.status}: {body_preview!r}"
                    raise APIResponseError(msg)
                try:
                    payload = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as exc:
                    body_preview = (await response.text())[:200]
                    msg = f"Buienalarm returned non-JSON body: {body_preview!r}"
                    raise APIParseError(msg) from exc
        except TimeoutError as exc:
            msg = f"Buienalarm timed out after {HTTP_TIMEOUT_SECONDS}s"
            raise APITimeoutError(msg) from exc
        except aiohttp.ClientError as exc:
            msg = f"Buienalarm transport error: {exc}"
            raise BuienalarmAPIError(msg) from exc

        fetched_at = datetime.now(UTC)
        try:
            return parse_buienalarm(payload, fetched_at=fetched_at)
        except APIParseError as exc:
            _LOGGER.warning("Buienalarm parse failed: %s", exc)
            raise BuienalarmAPIError(str(exc)) from exc
