"""Buienradar-specific error class."""

from __future__ import annotations

from ...models import RainForecastError


class BuienradarAPIError(RainForecastError):
    """Generic Buienradar API error."""
