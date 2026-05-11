"""Buienalarm parser tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.nl_rain_forecast.api.buienalarm import parse_buienalarm
from custom_components.nl_rain_forecast.models import APIParseError

from .conftest import load_fixture


def _fetched_at() -> datetime:
    return datetime(2026, 5, 8, 12, 0, tzinfo=UTC)


def _payload(name: str) -> dict:
    return json.loads(load_fixture(name))


def test_parses_dry_fixture_with_zero_values():
    forecast = parse_buienalarm(_payload("buienalarm_dry.json"), fetched_at=_fetched_at())
    assert forecast.source == "buienalarm"
    assert len(forecast.slots) == 24
    assert all(slot.value == 0.0 for slot in forecast.slots)


def test_parses_active_fixture():
    forecast = parse_buienalarm(_payload("buienalarm_active.json"), fetched_at=_fetched_at())
    assert len(forecast.slots) == 24
    assert forecast.peak_intensity == 5.0
    # 5-minute spacing
    assert forecast.slots[1].time - forecast.slots[0].time == timedelta(seconds=300)


def test_slots_are_timezone_aware_utc():
    forecast = parse_buienalarm(_payload("buienalarm_dry.json"), fetched_at=_fetched_at())
    assert forecast.slots[0].time.tzinfo is UTC


def test_negative_values_are_floored_to_zero():
    payload = {"start": 1714978800, "delta": 300, "precip": [-0.5, 0.3]}
    forecast = parse_buienalarm(payload, fetched_at=_fetched_at())
    assert forecast.slots[0].value == 0.0
    assert forecast.slots[1].value == 0.3


def test_missing_start_raises():
    with pytest.raises(APIParseError):
        parse_buienalarm({"delta": 300, "precip": [0.0]}, fetched_at=_fetched_at())


def test_missing_precip_raises():
    with pytest.raises(APIParseError):
        parse_buienalarm({"start": 1, "delta": 300}, fetched_at=_fetched_at())


def test_empty_precip_raises():
    with pytest.raises(APIParseError):
        parse_buienalarm({"start": 1, "delta": 300, "precip": []}, fetched_at=_fetched_at())


def test_success_false_raises():
    with pytest.raises(APIParseError):
        parse_buienalarm(
            {"success": False, "start": 1, "delta": 300, "precip": [0.0]},
            fetched_at=_fetched_at(),
        )


def test_non_dict_payload_raises():
    with pytest.raises(APIParseError):
        parse_buienalarm([], fetched_at=_fetched_at())  # ty: ignore[invalid-argument-type]


def test_non_positive_delta_falls_back_to_default():
    payload = {"start": 1714978800, "delta": 0, "precip": [0.0, 1.0]}
    forecast = parse_buienalarm(payload, fetched_at=_fetched_at())
    assert forecast.slots[1].time - forecast.slots[0].time == timedelta(seconds=300)


def test_skips_non_numeric_slot_values():
    payload = {
        "start": 1714978800,
        "delta": 300,
        "precip": [0.0, "garbage", 1.5, None, 0.0],
    }
    forecast = parse_buienalarm(payload, fetched_at=_fetched_at())
    assert [slot.value for slot in forecast.slots] == [0.0, 1.5, 0.0]
