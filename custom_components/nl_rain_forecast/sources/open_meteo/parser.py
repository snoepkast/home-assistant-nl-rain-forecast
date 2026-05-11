"""
Pure parser for the Open-Meteo ``minutely_15`` precipitation response.

Open-Meteo returns precipitation as **mm accumulated in the preceding
15-minute window**, sampled at 15-minute boundaries (`:00`, `:15`, `:30`,
`:45`). To align with the cadence of the other sources, the parser:

1. Converts each 15-min accumulation to a mean mm/h intensity.
2. Linearly interpolates between consecutive intensities to fill in two
   intermediate 5-min slots per 15-min gap.
3. Truncates / pads to deliver an even 5-min spaced series.

The interpolation is honest about its source: the underlying model only
has 15-min resolution, the interpolated 5-min values are a visual
alignment, not new information.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ...models import APIParseError, Forecast, ForecastSlot
from .const import (
    ID,
    MM_PER_INTERVAL_TO_MM_PER_HOUR,
    TARGET_INTERVAL_MINUTES,
    UPSTREAM_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

_SUB_SLOTS_PER_UPSTREAM = UPSTREAM_INTERVAL_MINUTES // TARGET_INTERVAL_MINUTES  # 3


def parse_open_meteo(payload: dict[str, Any], *, fetched_at: datetime) -> Forecast:
    """Parse an Open-Meteo ``minutely_15`` response into an interpolated Forecast."""
    if not isinstance(payload, dict):
        msg = f"Open-Meteo payload is not an object: {type(payload).__name__}"
        raise APIParseError(msg)

    if payload.get("error") is True:
        reason = payload.get("reason", "unknown")
        msg = f"Open-Meteo returned error: {reason}"
        raise APIParseError(msg)

    block = payload.get("minutely_15")
    if not isinstance(block, dict):
        msg = "Open-Meteo payload missing 'minutely_15' object"
        raise APIParseError(msg)

    times_raw = block.get("time")
    precip_raw = block.get("precipitation")
    if not isinstance(times_raw, list) or not isinstance(precip_raw, list):
        msg = "Open-Meteo 'minutely_15.time' and 'precipitation' must be lists"
        raise APIParseError(msg)

    if len(times_raw) != len(precip_raw):
        msg = (
            f"Open-Meteo time/precipitation arrays differ in length: "
            f"{len(times_raw)} vs {len(precip_raw)}"
        )
        raise APIParseError(msg)

    coarse = _to_coarse_slots(times_raw, precip_raw)
    if len(coarse) < 2:  # noqa: PLR2004
        msg = (
            "Open-Meteo returned fewer than 2 usable 15-min slots; "
            "cannot interpolate to 5-min cadence"
        )
        raise APIParseError(msg)

    fine_slots = _interpolate_to_target_cadence(coarse)
    return Forecast(source=ID, fetched_at=fetched_at, slots=tuple(fine_slots))


def _to_coarse_slots(
    times_raw: list[Any],
    precip_raw: list[Any],
) -> list[ForecastSlot]:
    """Build mm/h-valued ForecastSlots at the upstream's 15-min cadence."""
    slots: list[ForecastSlot] = []
    for raw_time, raw_value in zip(times_raw, precip_raw, strict=True):
        if raw_value is None:
            _LOGGER.debug("Open-Meteo: skipping null precipitation at %s", raw_time)
            continue
        if not isinstance(raw_value, (int, float)):
            _LOGGER.debug(
                "Open-Meteo: skipping non-numeric precipitation %r at %s",
                raw_value,
                raw_time,
            )
            continue
        if not isinstance(raw_time, str):
            _LOGGER.debug("Open-Meteo: skipping non-string time %r", raw_time)
            continue
        try:
            parsed_time = _parse_iso_utc(raw_time)
        except ValueError:
            _LOGGER.debug("Open-Meteo: skipping unparseable time %r", raw_time)
            continue
        intensity_mm_per_h = max(0.0, float(raw_value) * MM_PER_INTERVAL_TO_MM_PER_HOUR)
        slots.append(ForecastSlot(time=parsed_time, value=round(intensity_mm_per_h, 1)))
    return slots


def _parse_iso_utc(value: str) -> datetime:
    """
    Parse an ISO 8601 timestamp, treating naive strings as UTC.

    Open-Meteo returns naive strings when ``timezone=GMT`` (our default).
    """
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _interpolate_to_target_cadence(coarse: list[ForecastSlot]) -> list[ForecastSlot]:
    """Linearly interpolate ``coarse`` (15-min cadence) to 5-min cadence."""
    fine: list[ForecastSlot] = []
    sub_interval = timedelta(minutes=TARGET_INTERVAL_MINUTES)
    for i in range(len(coarse) - 1):
        start = coarse[i]
        end = coarse[i + 1]
        delta = end.value - start.value
        for k in range(_SUB_SLOTS_PER_UPSTREAM):
            value = start.value + delta * k / _SUB_SLOTS_PER_UPSTREAM
            fine.append(
                ForecastSlot(
                    time=start.time + k * sub_interval,
                    value=max(0.0, round(value, 1)),
                )
            )
    # Final coarse slot has no successor to interpolate against; carry verbatim.
    fine.append(coarse[-1])
    return fine
