"""Config flow tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nl_rain_forecast.const import (
    CONF_LOCATION_NAME,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

# Inside the NL bbox.
HOME_LAT, HOME_LON = 52.3676, 4.9041
# Outside the NL bbox (Paris).
PARIS_LAT, PARIS_LON = 48.8566, 2.3522


def _user_input(**overrides) -> dict:
    base = {
        CONF_LOCATION_NAME: "Home",
        CONF_LATITUDE: HOME_LAT,
        CONF_LONGITUDE: HOME_LON,
        CONF_UPDATE_INTERVAL: 5,
    }
    base.update(overrides)
    return base


@pytest.fixture
def _mock_probe_ok():
    with patch(
        "custom_components.nl_rain_forecast.config_flow._probe_sources",
        return_value={},
    ) as p:
        yield p


@pytest.fixture
def _mock_probe_fail():
    with patch(
        "custom_components.nl_rain_forecast.config_flow._probe_sources",
        return_value={"buienradar": "boom"},
    ) as p:
        yield p


async def test_user_form_shown_first(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("_mock_probe_ok")
async def test_happy_path_creates_entry(hass):
    init = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(init["flow_id"], _user_input())
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"][CONF_LATITUDE] == HOME_LAT
    assert result["options"][CONF_UPDATE_INTERVAL] == 5


@pytest.mark.usefixtures("_mock_probe_ok")
async def test_outside_netherlands_shows_error(hass):
    init = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        init["flow_id"],
        _user_input(latitude=PARIS_LAT, longitude=PARIS_LON),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "outside_netherlands"}


@pytest.mark.usefixtures("_mock_probe_fail")
async def test_api_unreachable_shows_error(hass):
    init = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(init["flow_id"], _user_input())
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "api_unreachable"}


@pytest.mark.usefixtures("_mock_probe_ok")
async def test_duplicate_entry_aborts(hass):
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{round(HOME_LAT, 4)}_{round(HOME_LON, 4)}",
        data={
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: HOME_LAT,
            CONF_LONGITUDE: HOME_LON,
        },
    )
    existing.add_to_hass(hass)

    init = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(init["flow_id"], _user_input())
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_interval(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="52.0_5.0",
        data={
            CONF_LOCATION_NAME: "Home",
            CONF_LATITUDE: 52.0,
            CONF_LONGITUDE: 5.0,
        },
        options={CONF_UPDATE_INTERVAL: 5},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 15}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_UPDATE_INTERVAL] == 15
