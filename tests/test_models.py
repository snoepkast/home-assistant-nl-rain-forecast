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


# ---------------------------------------------------------------------------
# in_forward_window — alignment of disparate upstream cadences
# ---------------------------------------------------------------------------


def test_in_forward_window_keeps_slots_within_two_hour_window():
    """All five 5-min slots from now sit inside the default 2h window."""
    fc = _make([0.0, 0.5, 1.0, 0.0, 0.0])
    aligned = fc.in_forward_window()
    assert len(aligned.slots) == 5


def test_in_forward_window_drops_past_slots():
    """Slots before `floor(now, 5min)` get filtered out."""
    base = _at(0)
    past_slots = build_slots(base - timedelta(minutes=10), [9.0, 9.0])
    future_slots = build_slots(base, [1.0, 1.0, 1.0])
    fc = Forecast(source="test", fetched_at=base, slots=past_slots + future_slots)
    aligned = fc.in_forward_window()
    # 9.0 past slots dropped; first slot of aligned is the `base` slot.
    assert len(aligned.slots) == 3
    assert aligned.slots[0].time == base
    assert aligned.slots[0].value == 1.0


def test_in_forward_window_drops_slots_past_window_end():
    """Slots beyond floor(now, 5min) + 2h get filtered out."""
    base = _at(0)
    # 30 slots * 5 min = 150 min = 2h30m. Only the first 25 (= 2h) sit
    # inside the window because the comparison is inclusive on both ends.
    fc = Forecast(
        source="test",
        fetched_at=base,
        slots=build_slots(base, [0.0] * 30),
    )
    aligned = fc.in_forward_window()
    assert len(aligned.slots) == 25


def test_in_forward_window_anchors_on_explicit_now():
    """An explicit `now=` overrides fetched_at as the floor anchor."""
    fc = _make([1.0, 2.0, 3.0, 4.0, 5.0])
    # Anchor 10 min ahead → window starts at _at(10), so first two slots
    # (at 0 and 5 min) drop out.
    aligned = fc.in_forward_window(now=_at(10))
    assert len(aligned.slots) == 3
    assert aligned.slots[0].value == 3.0


def test_in_forward_window_floors_unaligned_anchor_to_5min():
    """A 14:04 anchor floors to 14:00, not 14:05."""
    base = datetime(2026, 5, 8, 14, 0, tzinfo=UTC)
    fc = Forecast(
        source="test",
        fetched_at=base,
        slots=build_slots(base, [1.0, 2.0, 3.0]),
    )
    aligned = fc.in_forward_window(now=base + timedelta(minutes=4))
    # Floor of 14:04 → 14:00, so all three slots (14:00/14:05/14:10) stay.
    assert len(aligned.slots) == 3


def test_in_forward_window_preserves_source_and_fetched_at():
    fc = _make([1.0])
    aligned = fc.in_forward_window()
    assert aligned.source == fc.source
    assert aligned.fetched_at == fc.fetched_at


def test_in_forward_window_empty_when_all_slots_are_old():
    """If the entire forecast is in the past, the result is empty."""
    base = _at(0)
    old_slots = build_slots(base - timedelta(hours=3), [1.0, 1.0, 1.0])
    fc = Forecast(source="test", fetched_at=base, slots=old_slots)
    aligned = fc.in_forward_window()
    assert aligned.slots == ()
