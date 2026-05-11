"""Unit tests for the Forecast domain model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.nl_rain_forecast.models import Forecast, build_slots


def _at(minute: int) -> datetime:
    return datetime(2026, 5, 8, 14, 0, tzinfo=UTC) + timedelta(minutes=minute)


def _make(values: list[float]) -> Forecast:
    base = _at(0)
    slots = build_slots(base, values)
    return Forecast(source="test", fetched_at=base, slots=slots)


def test_empty_forecast_returns_zero_and_none():
    fc = Forecast(source="test", fetched_at=_at(0), slots=())
    assert fc.current_intensity == 0.0
    assert fc.peak_intensity == 0.0
    assert fc.peak_time is None
    assert fc.total_precipitation == 0.0
    assert fc.next_rain_in_minutes() is None
    assert fc.next_dry_in_minutes() is None


def test_dry_forecast():
    fc = _make([0.0] * 5)
    assert fc.current_intensity == 0.0
    assert fc.peak_intensity == 0.0
    assert fc.peak_time is None
    assert fc.total_precipitation == 0.0
    # Currently dry, no rain coming -> both None
    assert fc.next_rain_in_minutes() is None
    assert fc.next_dry_in_minutes() is None


def test_active_forecast_peak_and_total():
    # 2.0 mm/h for 15 min then dry — total ≈ 0.5 mm
    fc = _make([2.0, 2.0, 2.0, 0.0, 0.0])
    assert fc.peak_intensity == 2.0
    assert fc.peak_time == _at(0)
    assert fc.total_precipitation == 0.5  # 2.0 * 0.25h


def test_next_rain_when_currently_dry():
    fc = _make([0.0, 0.0, 1.0, 1.0, 0.0])
    assert fc.next_rain_in_minutes() == 10  # third slot, 10 min in
    assert fc.next_dry_in_minutes() is None


def test_next_dry_when_currently_raining():
    fc = _make([1.0, 1.0, 0.0, 0.0, 0.0])
    assert fc.next_rain_in_minutes() is None
    assert fc.next_dry_in_minutes() == 10  # third slot


def test_peak_time_picks_first_max_when_tied():
    fc = _make([1.0, 2.0, 2.0, 1.0])
    assert fc.peak_intensity == 2.0
    assert fc.peak_time == _at(5)


def test_total_precipitation_with_single_slot_is_zero():
    fc = _make([5.0])
    assert fc.total_precipitation == 0.0
