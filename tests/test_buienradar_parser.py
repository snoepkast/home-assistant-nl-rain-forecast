"""Buienradar parser tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise

import pytest

from custom_components.nl_rain_forecast.models import APIParseError
from custom_components.nl_rain_forecast.sources.buienradar.const import (
    TIMEZONE as DUTCH_TZ,
)
from custom_components.nl_rain_forecast.sources.buienradar.parser import parse_buienradar

from .conftest import load_fixture


def _fetched_at(hour: int = 14, minute: int = 0) -> datetime:
    return datetime(2026, 5, 8, hour, minute, tzinfo=DUTCH_TZ)


def test_parses_dry_fixture_to_25_zero_slots():
    forecast = parse_buienradar(
        load_fixture("buienradar_dry.txt"),
        fetched_at=_fetched_at(),
    )
    assert forecast.source == "buienradar"
    assert len(forecast.slots) == 25
    assert all(slot.value == 0.0 for slot in forecast.slots)


def test_parses_active_fixture_with_rounded_intensity():
    forecast = parse_buienradar(
        load_fixture("buienradar_active.txt"),
        fetched_at=_fetched_at(),
    )
    assert len(forecast.slots) == 25
    # Intensity 109 → exactly 1.0 mm/h.
    assert forecast.slots[3].value == 1.0
    # Intensity 077 → 10**((77-109)/32) = 10**-1 = 0.1 mm/h.
    assert forecast.slots[1].value == 0.1
    # Peak at intensity 141 → 10**1 = 10.0 mm/h.
    assert forecast.peak_intensity == 10.0


def test_slots_are_chronologically_increasing():
    forecast = parse_buienradar(
        load_fixture("buienradar_active.txt"),
        fetched_at=_fetched_at(),
    )
    times = [slot.time for slot in forecast.slots]
    assert times == sorted(times)
    # 5-minute spacing
    deltas = {(b - a) for a, b in pairwise(times)}
    assert deltas == {timedelta(minutes=5)}


def test_handles_midnight_rollover():
    """The extreme fixture starts at 23:50 and rolls past midnight."""
    forecast = parse_buienradar(
        load_fixture("buienradar_extreme.txt"),
        fetched_at=_fetched_at(hour=23, minute=45),
    )
    assert len(forecast.slots) == 25
    times = [slot.time for slot in forecast.slots]
    # Slots remain strictly chronological across midnight — this is the
    # invariant we actually care about; .day or wall-clock checks would
    # be TZ-dependent.
    assert times == sorted(times)
    # The slot at HH:MM=00:00 (in upstream's local time) lands exactly
    # 10 minutes after the slot at 23:50.
    assert times[2] - times[0] == timedelta(minutes=10)
    # The day-rolling produces a span >= 1 hour across the 25-slot window.
    assert times[-1] - times[0] >= timedelta(hours=1)


def test_intensity_clipped_to_zero_for_value_zero():
    forecast = parse_buienradar(
        "000|14:00\n",
        fetched_at=_fetched_at(),
    )
    assert forecast.slots[0].value == 0.0


def test_extreme_intensity_yields_positive_finite_value():
    """The Buienradar formula is uncapped; just assert no overflow / negative."""
    forecast = parse_buienradar(
        "255|14:00\n",
        fetched_at=_fetched_at(),
    )
    assert forecast.slots[0].value > 0
    assert forecast.slots[0].value == round(forecast.slots[0].value, 1)


def test_empty_payload_raises():
    with pytest.raises(APIParseError):
        parse_buienradar("", fetched_at=_fetched_at())


def test_garbage_payload_raises():
    with pytest.raises(APIParseError):
        parse_buienradar("not a forecast at all", fetched_at=_fetched_at())


def test_skips_unparseable_lines_keeps_valid_ones():
    payload = "garbage\n000|14:00\nbroken|line\n077|14:05\n"
    forecast = parse_buienradar(payload, fetched_at=_fetched_at())
    assert len(forecast.slots) == 2
    assert forecast.slots[0].value == 0.0
    assert forecast.slots[1].value == 0.1


def test_slots_are_normalized_to_utc():
    """Every parser emits UTC datetimes so sources share one timezone."""
    forecast = parse_buienradar(
        "000|14:00\n",
        fetched_at=_fetched_at(),
    )
    slot_time = forecast.slots[0].time
    assert slot_time.utcoffset() == timedelta(0)
    # The wall-clock-in-Amsterdam interpretation is preserved — 14:00
    # Amsterdam in May (CEST = +02:00) is 12:00 UTC.
    assert slot_time.hour == 12
    assert slot_time.minute == 0
