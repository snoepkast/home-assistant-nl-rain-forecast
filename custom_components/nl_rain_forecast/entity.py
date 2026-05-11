"""Base entity for the NL Rain Forecast integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import NLRainForecastCoordinator


class NLRainForecastEntity(CoordinatorEntity["NLRainForecastCoordinator"]):
    """Common base: one device per config entry, attribution per source."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NLRainForecastCoordinator,
        *,
        location_name: str,
    ) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=location_name,
            manufacturer="NL Rain Forecast",
            model="Rain nowcast",
            entry_type=None,
        )
