"""
Buienradar nowcast client.

Endpoint: ``https://gpsgadget.buienradar.nl/data/raintext?lat={lat}&lon={lon}``

Response: 25 plain-text lines, each ``INTENSITY|HH:MM`` where INTENSITY is a
0-255 integer encoding rainfall via ``mm/h = 10 ** ((value - 109) / 32)``.
HH:MM is local Dutch time (Europe/Amsterdam).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Final
from zoneinfo import ZoneInfo

import aiohttp

from ..const import HTTP_TIMEOUT_SECONDS, USER_AGENT
from ..models import (
    APIParseError,
    APIResponseError,
    APITimeoutError,
    BuienradarAPIError,
    Forecast,
    ForecastSlot,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_LOGGER = logging.getLogger(__name__)

BUIENRADAR_URL: Final = "https://gpsgadget.buienradar.nl/data/raintext"
DUTCH_TZ: Final = ZoneInfo("Europe/Amsterdam")
SOURCE: Final = "buienradar"

_INTENSITY_MAX = 255
_FORMULA_SHIFT = 109
_FORMULA_DIVISOR = 32


def _intensity_to_mm_per_hour(value: int) -> float:
    """Convert Buienradar's 0-255 intensity code to mm/h, rounded to 1 decimal."""
    if value <= 0:
        return 0.0
    mm_per_hour = 10 ** ((value - _FORMULA_SHIFT) / _FORMULA_DIVISOR)
    return round(mm_per_hour, 1)


def parse_buienradar(
    payload: str,
    *,
    fetched_at: datetime,
    tz: ZoneInfo = DUTCH_TZ,
) -> Forecast:
    """
    Parse a Buienradar raintext payload into a Forecast.

    Args:
        payload: Raw text body from the Buienradar endpoint.
        fetched_at: When the payload was fetched (timezone-aware). Used as
            the reference for date-rollover detection — Buienradar only
            returns ``HH:MM`` so we must derive the date.
        tz: Timezone the upstream HH:MM is expressed in. Defaults to
            ``Europe/Amsterdam``.

    Returns:
        Forecast with chronologically ordered slots.

    Raises:
        APIParseError: If the payload is empty or contains no valid lines.

    """
    if not payload or not payload.strip():
        msg = "Buienradar returned an empty payload"
        raise APIParseError(msg)

    raw_slots = list(_iter_raw_slots(payload))
    if not raw_slots:
        msg = "Buienradar payload contained no valid INTENSITY|HH:MM lines"
        raise APIParseError(msg)

    base_date = fetched_at.astimezone(tz).date()
    slots: list[ForecastSlot] = []
    previous_minutes_of_day: int | None = None
    day_offset = timedelta(0)

    for value, hh, mm in raw_slots:
        slot_minutes = hh * 60 + mm
        # Rollover: if the new HH:MM is earlier than the previous, we crossed
        # midnight. Add a day's offset to keep slots chronological.
        if previous_minutes_of_day is not None and slot_minutes < previous_minutes_of_day:
            day_offset += timedelta(days=1)
        previous_minutes_of_day = slot_minutes

        local_dt = datetime.combine(base_date, time(hh, mm), tzinfo=tz) + day_offset
        # If the very first parsed slot is more than ~12h before fetched_at,
        # the API rolled into yesterday-tomorrow boundary the other way; bump
        # everything forward a day.
        if not slots and (local_dt - fetched_at) < timedelta(hours=-12):
            local_dt += timedelta(days=1)
            day_offset += timedelta(days=1)
        slots.append(ForecastSlot(time=local_dt, value=_intensity_to_mm_per_hour(value)))

    return Forecast(source=SOURCE, fetched_at=fetched_at, slots=tuple(slots))


def _iter_raw_slots(payload: str) -> Iterable[tuple[int, int, int]]:
    """Yield (intensity, hour, minute) tuples for each parseable line."""
    for raw_line in payload.splitlines():
        line = raw_line.strip()
        if not line or "|" not in line:
            continue
        intensity_str, _, time_str = line.partition("|")
        try:
            intensity = int(intensity_str)
        except ValueError:
            _LOGGER.debug("Buienradar: skipping unparseable intensity %r", intensity_str)
            continue
        if not 0 <= intensity <= _INTENSITY_MAX:
            _LOGGER.debug("Buienradar: skipping out-of-range intensity %d", intensity)
            continue
        if ":" not in time_str:
            _LOGGER.debug("Buienradar: skipping line with no time %r", line)
            continue
        hh_str, _, mm_str = time_str.partition(":")
        try:
            hh = int(hh_str)
            mm = int(mm_str)
        except ValueError:
            _LOGGER.debug("Buienradar: skipping unparseable time %r", time_str)
            continue
        if not (0 <= hh < 24 and 0 <= mm < 60):  # noqa: PLR2004
            _LOGGER.debug("Buienradar: skipping invalid time %02d:%02d", hh, mm)
            continue
        yield intensity, hh, mm


class BuienradarClient:
    """Async HTTP client for the Buienradar raintext endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def async_get_forecast(self, lat: float, lon: float) -> Forecast:
        """Fetch and parse the forecast for ``lat``/``lon``."""
        params = {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"}
        headers = {"User-Agent": USER_AGENT, "Accept": "text/plain"}
        try:
            async with asyncio.timeout(HTTP_TIMEOUT_SECONDS):
                response = await self._session.get(
                    BUIENRADAR_URL,
                    params=params,
                    headers=headers,
                )
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

        fetched_at = datetime.now(DUTCH_TZ)
        try:
            return parse_buienradar(payload, fetched_at=fetched_at)
        except APIParseError as exc:
            _LOGGER.warning(
                "Buienradar parse failed (preview: %r): %s",
                payload[:200],
                exc,
            )
            raise BuienradarAPIError(str(exc)) from exc
