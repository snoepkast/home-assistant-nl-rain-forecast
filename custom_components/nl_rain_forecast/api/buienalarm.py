"""
Buienalarm forecast client.

Endpoint: ``https://cdn-secure.buienalarm.nl/api/3.4/forecast.php``

Response (JSON): ``{start, delta, precip, ...}`` where ``start`` is a Unix
timestamp (seconds), ``delta`` is the slot duration in seconds (typically
300), and ``precip`` is an array of mm/h floats.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import aiohttp

from ..const import HTTP_TIMEOUT_SECONDS, USER_AGENT
from ..models import (
    APIParseError,
    APIResponseError,
    APITimeoutError,
    BuienalarmAPIError,
    Forecast,
    ForecastSlot,
)

_LOGGER = logging.getLogger(__name__)

BUIENALARM_URL: Final = "https://cdn-secure.buienalarm.nl/api/3.4/forecast.php"
SOURCE: Final = "buienalarm"

DEFAULT_DELTA_SECONDS = 300


def parse_buienalarm(payload: dict[str, Any], *, fetched_at: datetime) -> Forecast:
    """Parse a Buienalarm JSON payload into a Forecast."""
    if not isinstance(payload, dict):
        msg = f"Buienalarm payload is not an object: {type(payload).__name__}"
        raise APIParseError(msg)

    if payload.get("success") is False:
        msg = "Buienalarm reported success=false"
        raise APIParseError(msg)

    start_raw = payload.get("start")
    precip_raw = payload.get("precip")
    delta_raw = payload.get("delta", DEFAULT_DELTA_SECONDS)

    if start_raw is None or precip_raw is None:
        msg = "Buienalarm payload missing required fields 'start' or 'precip'"
        raise APIParseError(msg)

    if not isinstance(precip_raw, list) or not precip_raw:
        msg = "Buienalarm 'precip' must be a non-empty list"
        raise APIParseError(msg)

    try:
        start_ts = int(start_raw)
        delta_seconds = int(delta_raw)
    except (TypeError, ValueError) as exc:
        msg = f"Buienalarm 'start'/'delta' not coercible to int: {exc}"
        raise APIParseError(msg) from exc

    if delta_seconds <= 0:
        _LOGGER.warning(
            "Buienalarm reported non-positive delta=%s, falling back to %s",
            delta_seconds,
            DEFAULT_DELTA_SECONDS,
        )
        delta_seconds = DEFAULT_DELTA_SECONDS

    base = datetime.fromtimestamp(start_ts, tz=UTC)
    interval = timedelta(seconds=delta_seconds)

    slots: list[ForecastSlot] = []
    for i, raw_value in enumerate(precip_raw):
        if not isinstance(raw_value, (int, float, str)):
            _LOGGER.debug("Buienalarm: skipping non-numeric value at index %d: %r", i, raw_value)
            continue
        try:
            value = float(raw_value)
        except TypeError, ValueError:
            _LOGGER.debug("Buienalarm: skipping non-numeric value at index %d: %r", i, raw_value)
            continue
        slots.append(
            ForecastSlot(
                time=base + i * interval,
                value=round(max(value, 0.0), 1),
            )
        )

    if not slots:
        msg = "Buienalarm payload had no parseable precip values"
        raise APIParseError(msg)

    return Forecast(source=SOURCE, fetched_at=fetched_at, slots=tuple(slots))


class BuienalarmClient:
    """Async HTTP client for the Buienalarm forecast endpoint."""

    def __init__(self, session: aiohttp.ClientSession, *, version: str = "0.1.0") -> None:
        self._session = session
        self._user_agent = f"{USER_AGENT}/{version}"

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""
        params = {
            "lat": f"{lat:.4f}",
            "lon": f"{lon:.4f}",
            "region": "nl",
            "unit": "mm/u",
        }
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        try:
            async with asyncio.timeout(HTTP_TIMEOUT_SECONDS):
                response = await self._session.get(
                    BUIENALARM_URL,
                    params=params,
                    headers=headers,
                )
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
