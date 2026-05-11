"""
Pure parser for the Buienalarm JSON payload.

Response shape: ``{start, delta, precip, ...}`` where ``start`` is a Unix
timestamp (seconds), ``delta`` is the slot duration in seconds (typically
300), and ``precip`` is an array of mm/h floats.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ...models import APIParseError, Forecast, ForecastSlot
from .const import DEFAULT_DELTA_SECONDS, ID

_LOGGER = logging.getLogger(__name__)


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

    return Forecast(source=ID, fetched_at=fetched_at, slots=tuple(slots))
