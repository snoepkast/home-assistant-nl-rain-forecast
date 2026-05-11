"""Config flow + options flow for NL Rain Forecast."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BuienalarmClient, BuienradarClient
from .const import (
    CONF_LOCATION_NAME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    LOGGER,
    MAX_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
    NL_LAT_MAX,
    NL_LAT_MIN,
    NL_LON_MAX,
    NL_LON_MIN,
)
from .models import RainForecastError

if TYPE_CHECKING:
    from collections.abc import Mapping


def _is_in_netherlands(lat: float, lon: float) -> bool:
    return NL_LAT_MIN <= lat <= NL_LAT_MAX and NL_LON_MIN <= lon <= NL_LON_MAX


def _unique_id(lat: float, lon: float) -> str:
    """Stable unique id from coordinates rounded to 4 decimals (~11m)."""
    return f"{round(lat, 4)}_{round(lon, 4)}"


class NLRainForecastConfigFlow(ConfigFlow, domain=DOMAIN):
    """User-driven config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Single-step setup: name, lat, lon, update interval."""
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = float(user_input[CONF_LATITUDE])
            lon = float(user_input[CONF_LONGITUDE])

            if not _is_in_netherlands(lat, lon):
                errors["base"] = "outside_netherlands"
            else:
                await self.async_set_unique_id(_unique_id(lat, lon))
                self._abort_if_unique_id_configured()

                source_errors = await _probe_sources(self.hass, lat, lon)
                if source_errors:
                    errors["base"] = "api_unreachable"
                    LOGGER.warning("Config flow API probe failed: %s", source_errors)
                else:
                    return self.async_create_entry(
                        title=user_input[CONF_LOCATION_NAME],
                        data={
                            CONF_LOCATION_NAME: user_input[CONF_LOCATION_NAME],
                            CONF_LATITUDE: lat,
                            CONF_LONGITUDE: lon,
                        },
                        options={
                            CONF_UPDATE_INTERVAL: int(
                                user_input.get(
                                    CONF_UPDATE_INTERVAL,
                                    DEFAULT_UPDATE_INTERVAL_MINUTES,
                                )
                            ),
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self.hass, user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:  # noqa: ARG004
        return NLRainForecastOptionsFlow()


class NLRainForecastOptionsFlow(OptionsFlow):
    """Options flow: only the update interval is reconfigurable."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_UPDATE_INTERVAL: int(user_input[CONF_UPDATE_INTERVAL]),
                },
            )

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVAL_MINUTES,
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=current,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL_MINUTES,
                            max=MAX_UPDATE_INTERVAL_MINUTES,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                },
            ),
        )


def _user_schema(
    hass: Any,
    previous: Mapping[str, Any] | None,
) -> vol.Schema:
    previous = previous or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_LOCATION_NAME,
                default=previous.get(CONF_LOCATION_NAME, "Home"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_LATITUDE,
                default=previous.get(CONF_LATITUDE, hass.config.latitude),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    step="any",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_LONGITUDE,
                default=previous.get(CONF_LONGITUDE, hass.config.longitude),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    step="any",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=previous.get(
                    CONF_UPDATE_INTERVAL,
                    DEFAULT_UPDATE_INTERVAL_MINUTES,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_UPDATE_INTERVAL_MINUTES,
                    max=MAX_UPDATE_INTERVAL_MINUTES,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
        }
    )


async def _probe_sources(hass: Any, lat: float, lon: float) -> dict[str, str]:
    """Probe both upstream APIs; return ``{source: error}`` for any failures."""
    session = async_get_clientsession(hass)
    buienradar = BuienradarClient(session)
    buienalarm = BuienalarmClient(session)

    errors: dict[str, str] = {}
    try:
        await buienradar.async_get_forecast(lat, lon)
    except RainForecastError as exc:
        errors["buienradar"] = str(exc)
    try:
        await buienalarm.async_get_forecast(lat, lon)
    except RainForecastError as exc:
        errors["buienalarm"] = str(exc)
    return errors
