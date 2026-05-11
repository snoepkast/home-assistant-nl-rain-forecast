"""Buienalarm-specific error class."""

from __future__ import annotations

from ...models import RainForecastError


class BuienalarmAPIError(RainForecastError):
    """Generic Buienalarm API error."""
