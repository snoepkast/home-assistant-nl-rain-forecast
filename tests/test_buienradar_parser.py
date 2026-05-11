"""Buienradar parser tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from custom_components.nl_rain_forecast.api.buienradar import (
    DUTCH_TZ,
    parse_buienradar,
)
from custom_components.nl_rain_forecast.models import APIParseError

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
    # First slot is on the start day, later slots roll to next day.
    times = [slot.time for slot in forecast.slots]
    assert times == sorted(times), "slots must remain chronological across midnight"
    # The slot at 00:00 is exactly 10 minutes after the slot at 23:50.
    assert times[2] - times[0] == timedelta(minutes=10)
    # Day rolled forward.
    assert times[0].day == 8
    assert times[2].day == 9


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


def test_dst_aware_datetimes_use_amsterdam_tz():
    """Slots must be timezone-aware in Europe/Amsterdam."""
    forecast = parse_buienradar(
        "000|14:00\n",
        fetched_at=_fetched_at(),
    )
    assert forecast.slots[0].time.tzinfo == ZoneInfo("Europe/Amsterdam")
