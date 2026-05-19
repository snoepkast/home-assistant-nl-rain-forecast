"""Domain models, exceptions, and forecast helpers for NL Rain Forecast."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RainForecastError(Exception):
    """Base error for the integration."""


class APITimeoutError(RainForecastError):
    """Upstream did not respond within the timeout."""


class APIResponseError(RainForecastError):
    """Upstream returned an unexpected status or body."""


class APIParseError(RainForecastError):
    """Upstream payload could not be parsed."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

# Minimum slots needed to *numerically integrate* mm/h over time deltas.
# Nothing to do with the count of upstream sources.
_MIN_SLOTS_FOR_NUMERICAL_INTEGRAL = 2

# Default forward-looking forecast window: the next 2 hours, sampled on
# 5-minute boundaries. Used by Forecast.in_forward_window().
_DEFAULT_FORECAST_WINDOW = timedelta(hours=2)
_DEFAULT_FORECAST_INTERVAL_MINUTES = 5


def _floor_to_minute_boundary(dt: datetime, interval_minutes: int) -> datetime:
    """
    Round ``dt`` DOWN to the nearest ``interval_minutes`` mark.

    Preserves ``tzinfo``. Used to align disparate-cadence forecasts to a
    common forward window starting at the most recent 5-minute boundary.
    """
    return dt.replace(
        minute=(dt.minute // interval_minutes) * interval_minutes,
        second=0,
        microsecond=0,
    )


@dataclass(frozen=True, slots=True)
class ForecastSlot:
    """A single 5-minute forecast slot."""

    time: datetime
    """Timezone-aware datetime that the slot represents."""

    value: float
    """Precipitation intensity in mm/h, rounded to 1 decimal."""


@dataclass(frozen=True, slots=True)
class Forecast:
    """A complete forecast for one location and one source."""

    source: str
    """Source identifier, matching :attr:`sources.Source.id`."""

    fetched_at: datetime
    """When the data was fetched (timezone-aware)."""

    slots: tuple[ForecastSlot, ...] = field(default_factory=tuple)
    """Forecast slots in chronological order, typically 5-minute spacing."""

    # ------------------------------------------------------------------
    # Derived attributes
    # ------------------------------------------------------------------

    @property
    def current_intensity(self) -> float:
        """First (current) slot intensity in mm/h, or 0.0 if no slots."""
        if not self.slots:
            return 0.0
        return self.slots[0].value

    @property
    def peak_intensity(self) -> float:
        """Maximum intensity across all slots in mm/h."""
        if not self.slots:
            return 0.0
        return max(slot.value for slot in self.slots)

    @property
    def peak_time(self) -> datetime | None:
        """Time of the first peak, or ``None`` if no rain."""
        if not self.slots:
            return None
        peak = max(self.slots, key=lambda s: s.value)
        if peak.value <= 0:
            return None
        return peak.time

    @property
    def total_precipitation(self) -> float:
        """
        Total expected rainfall over the forecast window in mm.

        Computed by integrating intensity (mm/h) over each slot's duration.
        Slot duration is inferred from neighbouring slots; the final slot
        reuses the previous interval. Returns 0.0 for empty/single-slot
        forecasts where integration is not meaningful.
        """
        if len(self.slots) < _MIN_SLOTS_FOR_NUMERICAL_INTEGRAL:
            return 0.0
        total_mm = 0.0
        for i, slot in enumerate(self.slots):
            if i + 1 < len(self.slots):
                duration = self.slots[i + 1].time - slot.time
            else:
                duration = self.slots[i].time - self.slots[i - 1].time
            hours = duration.total_seconds() / 3600
            total_mm += slot.value * hours
        return round(total_mm, 2)

    def next_rain_in_minutes(self, *, now: datetime | None = None) -> int | None:
        """
        Minutes until rain starts.

        Returns ``None`` if it's currently raining (first slot > 0) or no
        rain is expected anywhere in the window.
        """
        if not self.slots or self.slots[0].value > 0:
            return None
        reference = now or self.slots[0].time
        for slot in self.slots:
            if slot.value > 0:
                delta = slot.time - reference
                return max(0, int(delta.total_seconds() // 60))
        return None

    def next_dry_in_minutes(self, *, now: datetime | None = None) -> int | None:
        """
        Minutes until rain stops.

        Returns ``None`` if it's currently dry (first slot == 0) or rain
        continues through the entire window.
        """
        if not self.slots or self.slots[0].value <= 0:
            return None
        reference = now or self.slots[0].time
        for slot in self.slots:
            if slot.value <= 0:
                delta = slot.time - reference
                return max(0, int(delta.total_seconds() // 60))
        return None

    def in_forward_window(
        self,
        *,
        now: datetime | None = None,
        window: timedelta = _DEFAULT_FORECAST_WINDOW,
        interval_minutes: int = _DEFAULT_FORECAST_INTERVAL_MINUTES,
    ) -> Forecast:
        """
        Return a copy of this Forecast trimmed to a forward-looking window.

        The window starts at ``floor(now, interval_minutes)`` and extends
        ``window`` ahead. Past slots are dropped. Each upstream source has
        its own native start offset, so passing every Forecast through
        this method before display gives all sensors a common 5-min-
        aligned 2-hour window starting at the most recent 5-min mark.

        ``now`` defaults to :attr:`fetched_at`.
        """
        anchor = now if now is not None else self.fetched_at
        start = _floor_to_minute_boundary(anchor, interval_minutes)
        end = start + window
        aligned = tuple(s for s in self.slots if start <= s.time <= end)
        return Forecast(source=self.source, fetched_at=self.fetched_at, slots=aligned)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def build_slots(
    base_time: datetime,
    values: Iterable[float],
    interval: timedelta = timedelta(minutes=5),
) -> tuple[ForecastSlot, ...]:
    """Build a tuple of ForecastSlots starting at ``base_time``."""
    return tuple(
        ForecastSlot(time=base_time + i * interval, value=round(value, 1))
        for i, value in enumerate(values)
    )
