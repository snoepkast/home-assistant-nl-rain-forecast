"""Async HTTP client for the Buienradar raintext endpoint."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp

from ...const import HTTP_TIMEOUT_SECONDS, USER_AGENT
from ...models import APIParseError, APIResponseError, APITimeoutError
from .const import TIMEZONE, URL
from .errors import BuienradarAPIError
from .parser import parse_buienradar

if TYPE_CHECKING:
    from ...models import Forecast

_LOGGER = logging.getLogger(__name__)


class BuienradarClient:
    """HTTP wrapper around the Buienradar raintext endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""
        params = {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"}
        headers = {"User-Agent": USER_AGENT, "Accept": "text/plain"}
        try:
            async with asyncio.timeout(HTTP_TIMEOUT_SECONDS):
                response = await self._session.get(URL, params=params, headers=headers)
                if response.status >= 400:  # noqa: PLR2004
                    body_preview = (await response.text())[:200]
                    msg = f"Buienradar HTTP {response.status}: {body_preview!r}"
                    raise APIResponseError(msg)
                payload = await response.text()
        except TimeoutError as exc:
            msg = f"Buienradar timed out after {HTTP_TIMEOUT_SECONDS}s"
            raise APITimeoutError(msg) from exc
        except aiohttp.ClientError as exc:
            msg = f"Buienradar transport error: {exc}"
            raise BuienradarAPIError(msg) from exc

        fetched_at = datetime.now(TIMEZONE)
        try:
            return parse_buienradar(payload, fetched_at=fetched_at)
        except APIParseError as exc:
            _LOGGER.warning(
                "Buienradar parse failed (preview: %r): %s",
                payload[:200],
                exc,
            )
            raise BuienradarAPIError(str(exc)) from exc
