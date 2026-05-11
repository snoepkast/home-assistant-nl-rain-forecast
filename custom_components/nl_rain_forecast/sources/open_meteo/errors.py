"""Open-Meteo-specific error class."""

from __future__ import annotations

from ...models import RainForecastError


class OpenMeteoAPIError(RainForecastError):
    """Generic Open-Meteo API error."""
