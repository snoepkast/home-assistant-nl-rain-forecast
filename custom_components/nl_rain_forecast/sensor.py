"""Sensor platform: one rain-intensity sensor per data source per device."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from .const import (
    ATTRIBUTION_BUIENALARM,
    ATTRIBUTION_BUIENRADAR,
    SOURCE_BUIENALARM,
    SOURCE_BUIENRADAR,
)
from .entity import NLRainForecastEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NLRainForecastCoordinator
    from .data import NLRainForecastConfigEntry
    from .models import Forecast


@dataclass(frozen=True, kw_only=True, slots=True)
class RainSensorDescription(SensorEntityDescription):
    """Sensor description carrying the source identifier."""

    source: str
    attribution: str


SENSOR_DESCRIPTIONS: tuple[RainSensorDescription, ...] = (
    RainSensorDescription(
        key="rain_forecast_buienradar",
        translation_key="rain_forecast_buienradar",
        source=SOURCE_BUIENRADAR,
        attribution=ATTRIBUTION_BUIENRADAR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mm/h",
        suggested_display_precision=1,
    ),
    RainSensorDescription(
        key="rain_forecast_buienalarm",
        translation_key="rain_forecast_buienalarm",
        source=SOURCE_BUIENALARM,
        attribution=ATTRIBUTION_BUIENALARM,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mm/h",
        suggested_display_precision=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: NLRainForecastConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register one sensor per configured source."""
    runtime = entry.runtime_data
    async_add_entities(
        RainForecastSensor(
            coordinator=runtime.coordinator,
            description=description,
            location_name=runtime.location_name,
            entry_id=entry.entry_id,
        )
        for description in SENSOR_DESCRIPTIONS
    )


class RainForecastSensor(NLRainForecastEntity, SensorEntity):
    """Current rain intensity (mm/h) for one source, with forecast attributes."""

    entity_description: RainSensorDescription

    def __init__(
        self,
        *,
        coordinator: NLRainForecastCoordinator,
        description: RainSensorDescription,
        location_name: str,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, location_name=location_name)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.source}"
        self._attr_attribution = description.attribution

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _forecast(self) -> Forecast | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.source)

    # ------------------------------------------------------------------
    # SensorEntity overrides
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Available when both the coordinator and this source have data."""
        return super().available and self._forecast() is not None

    @property
    def native_value(self) -> float | None:
        forecast = self._forecast()
        if forecast is None or not forecast.slots:
            return None
        return forecast.current_intensity

    @property
    def icon(self) -> str:
        forecast = self._forecast()
        if forecast is not None and forecast.current_intensity > 0:
            return "mdi:weather-pouring"
        return "mdi:weather-cloudy"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        forecast = self._forecast()
        if forecast is None:
            return {}

        return {
            "forecast": [
                {"time": slot.time.isoformat(), "value": slot.value} for slot in forecast.slots
            ],
            "peak_intensity": forecast.peak_intensity,
            "peak_time": (forecast.peak_time.isoformat() if forecast.peak_time else None),
            "total_precipitation": forecast.total_precipitation,
            "next_rain_in_minutes": forecast.next_rain_in_minutes(),
            "next_dry_in_minutes": forecast.next_dry_in_minutes(),
            "source": forecast.source,
            "last_updated": forecast.fetched_at.isoformat(),
        }
