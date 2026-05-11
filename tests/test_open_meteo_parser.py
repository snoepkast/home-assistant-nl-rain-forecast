"""Open-Meteo parser tests, including 15→5 min interpolation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import pytest

from custom_components.nl_rain_forecast.models import APIParseError
from custom_components.nl_rain_forecast.sources.open_meteo.parser import parse_open_meteo

from .conftest import load_fixture


def _fetched_at() -> datetime:
    return datetime(2026, 5, 8, 14, 0, tzinfo=UTC)


def _payload(name: str) -> dict:
    return json.loads(load_fixture(name))


# --- Happy paths ----------------------------------------------------------


def test_parses_dry_fixture_yields_25_zero_slots():
    forecast = parse_open_meteo(_payload("open_meteo_dry.json"), fetched_at=_fetched_at())
    assert forecast.source == "open_meteo"
    assert len(forecast.slots) == 25
    assert all(slot.value == 0.0 for slot in forecast.slots)


def test_parses_active_fixture_yields_25_slots():
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    assert len(forecast.slots) == 25


def test_slots_are_5_minutes_apart():
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    deltas = {(b.time - a.time) for a, b in pairwise(forecast.slots)}
    assert deltas == {timedelta(minutes=5)}


def test_slots_are_utc():
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    assert all(slot.time.tzinfo is UTC for slot in forecast.slots)


# --- Interpolation behaviour ---------------------------------------------


def test_interpolation_converts_mm_per_15min_to_mm_per_hour():
    """Upstream 0.25 mm / 15 min == 1.0 mm/h."""
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    # Second upstream slot (t=14:15) had 0.25 mm; matches the 4th fine slot (t=14:15).
    boundary_slot = forecast.slots[3]
    assert boundary_slot.time == datetime(2026, 5, 8, 14, 15, tzinfo=UTC)
    assert boundary_slot.value == 1.0


def test_interpolation_fills_intermediate_5min_slots_linearly():
    """Between coarse slots 0.0 and 1.0 mm/h, sub-slots step 0.0 → 0.3 → 0.7."""
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    # Slots 0/1/2 sit between coarse 0.0 (t=14:00) and 1.0 (t=14:15).
    assert forecast.slots[0].value == 0.0
    assert forecast.slots[1].value == 0.3  # 1.0 * 1/3 rounded
    assert forecast.slots[2].value == 0.7  # 1.0 * 2/3 rounded


def test_peak_intensity_matches_max_upstream_intensity():
    """0.5 mm/15min upstream → 2.0 mm/h peak."""
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    assert forecast.peak_intensity == 2.0
    assert forecast.peak_time == datetime(2026, 5, 8, 14, 30, tzinfo=UTC)


def test_final_coarse_slot_carries_through_verbatim():
    """The final upstream slot has no successor; it is appended as-is at t=16:00."""
    forecast = parse_open_meteo(_payload("open_meteo_active.json"), fetched_at=_fetched_at())
    last = forecast.slots[-1]
    assert last.time == datetime(2026, 5, 8, 16, 0, tzinfo=UTC)
    assert last.value == 0.0


# --- Edge cases & error handling -----------------------------------------


def test_skips_null_precipitation_values():
    payload = _payload("open_meteo_active.json")
    payload["minutely_15"]["precipitation"][2] = None
    forecast = parse_open_meteo(payload, fetched_at=_fetched_at())
    # 8 valid upstream slots → 3*(8-1)+1 = 22 fine slots.
    assert len(forecast.slots) == 22


def test_skips_non_numeric_values():
    payload = _payload("open_meteo_active.json")
    payload["minutely_15"]["precipitation"][4] = "garbage"
    forecast = parse_open_meteo(payload, fetched_at=_fetched_at())
    assert len(forecast.slots) == 22


def test_negative_values_are_floored_to_zero():
    payload = _payload("open_meteo_active.json")
    payload["minutely_15"]["precipitation"][1] = -1.0
    forecast = parse_open_meteo(payload, fetched_at=_fetched_at())
    # First non-zero coarse slot is now 0.0; interpolation between 0.0 and 0.5 mm/15min
    # (= 0.0 and 2.0 mm/h) gives sub-slots 0.0, 0.7, 1.3 → boundary at 14:30 is 2.0.
    assert forecast.peak_intensity == 2.0


def test_empty_minutely_block_raises():
    payload = {"minutely_15": {"time": [], "precipitation": []}}
    with pytest.raises(APIParseError):
        parse_open_meteo(payload, fetched_at=_fetched_at())


def test_mismatched_array_lengths_raise():
    payload = {
        "minutely_15": {
            "time": ["2026-05-08T14:00", "2026-05-08T14:15"],
            "precipitation": [0.0],
        }
    }
    with pytest.raises(APIParseError):
        parse_open_meteo(payload, fetched_at=_fetched_at())


def test_missing_minutely_block_raises():
    with pytest.raises(APIParseError):
        parse_open_meteo({"latitude": 52.0}, fetched_at=_fetched_at())


def test_error_response_raises():
    with pytest.raises(APIParseError):
        parse_open_meteo(
            {"error": True, "reason": "lat/lon outside model domain"},
            fetched_at=_fetched_at(),
        )


def test_non_dict_payload_raises():
    with pytest.raises(APIParseError):
        parse_open_meteo([], fetched_at=_fetched_at())  # ty: ignore[invalid-argument-type]


def test_single_coarse_slot_cannot_interpolate():
    payload = {
        "minutely_15": {
            "time": ["2026-05-08T14:00"],
            "precipitation": [0.5],
        }
    }
    with pytest.raises(APIParseError):
        parse_open_meteo(payload, fetched_at=_fetched_at())


def test_iso_with_explicit_z_offset_is_accepted():
    payload = _payload("open_meteo_active.json")
    payload["minutely_15"]["time"] = [t + "Z" for t in payload["minutely_15"]["time"]]
    forecast = parse_open_meteo(payload, fetched_at=_fetched_at())
    assert len(forecast.slots) == 25
    assert forecast.slots[0].time == datetime(2026, 5, 8, 14, 0, tzinfo=UTC)
