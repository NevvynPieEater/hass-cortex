"""Integration tests run inside a real Home Assistant test harness."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.idratek_cortex.const import (
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.idratek_cortex.diagnostics import async_get_config_entry_diagnostics


@pytest.fixture(autouse=True)
def no_settle_delay(monkeypatch):
    monkeypatch.setattr("custom_components.idratek_cortex.coordinator.COMMAND_SETTLE_DELAY", 0)


def user_input(cortex, **override):
    data = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: cortex.port,
        CONF_USERNAME: "home",
        CONF_PASSWORD: "secret",
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    }
    data.update(override)
    return data


async def setup_entry(hass: HomeAssistant, cortex, **override) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_input(cortex, **override),
        unique_id=f"127.0.0.1:{cortex.port}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id_for(hass: HomeAssistant, entry, object_id: str, domain: str) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}_{object_id}")
    assert entity_id, f"no {domain} entity for Cortex object {object_id}"
    return entity_id


# ----------------------------------------------------------------- config flow


async def test_config_flow_success(hass: HomeAssistant, cortex) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(cortex))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == cortex.port
    await hass.async_block_till_done()


async def test_config_flow_wrong_password(hass: HomeAssistant, cortex) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(cortex, **{CONF_PASSWORD: "nope"})
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_permission"}


async def test_config_flow_cannot_connect(hass: HomeAssistant, cortex) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(cortex, **{CONF_PORT: 1})
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_duplicate(hass: HomeAssistant, cortex) -> None:
    await setup_entry(hass, cortex)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input(cortex))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input(cortex, **{CONF_PASSWORD: "secret"})
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()


async def test_options_flow(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 60
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval.total_seconds() == 60


# -------------------------------------------------------------------- entities


async def test_entities_created(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    assert len(hass.states.async_all("light")) == 21
    assert len(hass.states.async_all("cover")) == 13
    assert len(hass.states.async_all("switch")) == 1
    # Temperature objects are refused for this user, as on the real system.
    assert len(hass.states.async_all("sensor")) == 0
    coordinator = entry.runtime_data
    assert sum(r == "no_permission" for r in coordinator.skipped.values()) == 9


async def test_friendly_names_and_devices(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    main = hass.states.get(entity_id_for(hass, entry, "76", "light"))
    assert main.attributes["friendly_name"] == "Kitchen Main Lights"
    assert main.state == STATE_OFF

    bar = hass.states.get(entity_id_for(hass, entry, "379", "light"))
    assert bar.attributes["friendly_name"] == "Kitchen Breakfast Bar Lights"

    outside = hass.states.get(entity_id_for(hass, entry, "550", "light"))
    assert outside.attributes["friendly_name"] == "Outside Front Floodlight"

    devices = dr.async_get(hass)
    assert devices.async_get_device({(DOMAIN, f"{entry.entry_id}_hub")}) is not None
    kitchen = devices.async_get_device({(DOMAIN, f"{entry.entry_id}_room_kitchen")})
    assert kitchen is not None and kitchen.manufacturer == "Idratek"


async def test_light_turn_on_off(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    entity_id = entity_id_for(hass, entry, "525", "light")
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call("light", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert cortex.state["525"]["Set State (Output)"] == "100"
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call("light", "turn_off", {"entity_id": entity_id}, blocking=True)
    assert cortex.state["525"]["Set State (Output)"] == "0"
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_switch(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    entity_id = entity_id_for(hass, entry, "492", "switch")
    assert hass.states.get(entity_id).attributes["friendly_name"] == "Lounge AV Socket"
    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert cortex.state["492"]["Set State (Output)"] == "100"
    assert hass.states.get(entity_id).state == STATE_ON
    # the socket uses lower-case port names; check what was actually sent
    assert ("POST", "/api/v1/Objects.json/492?Turn%20on=1") in cortex.requests


async def test_cover_commands_and_raw_attributes(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    entity_id = entity_id_for(hass, entry, "880", "cover")
    state = hass.states.get(entity_id)
    assert state.state == "open"  # State 100 = open, as confirmed by the owner
    assert state.attributes["current_position"] == 34  # analogue 33.74 -> 34 %
    assert state.attributes["cortex_state"] == "100"
    assert state.attributes["cortex_position"] == "33.7424270131371"
    assert state.attributes["cortex_busy"] == "0"

    await hass.services.async_call("cover", "close_cover", {"entity_id": entity_id}, blocking=True)
    assert ("POST", "/api/v1/Objects.json/880?Close=1") in cortex.requests
    closed = hass.states.get(entity_id)
    assert closed.state == "closed"
    assert closed.attributes["current_position"] == 0
    assert closed.attributes["cortex_busy"] == "1"

    await hass.services.async_call("cover", "stop_cover", {"entity_id": entity_id}, blocking=True)
    assert ("POST", "/api/v1/Objects.json/880?Stop=1") in cortex.requests
    assert await hass.config_entries.async_unload(entry.entry_id)  # cancels timers


async def test_temperature_sensors_when_permitted(hass: HomeAssistant, cortex) -> None:
    # ASSUMES a "Temperature[ValueOut]" port: the real layout is not captured yet.
    cortex.blocked_types = set()
    entry = await setup_entry(hass, cortex)
    sensors = hass.states.async_all("sensor")
    assert len(sensors) == 9
    state = hass.states.get(entity_id_for(hass, entry, "82", "sensor"))
    assert state.state == "21.5"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["friendly_name"] == "Kitchen Temperature"


async def test_command_error_is_reported(hass: HomeAssistant, cortex) -> None:
    from homeassistant.exceptions import HomeAssistantError

    entry = await setup_entry(hass, cortex)
    entity_id = entity_id_for(hass, entry, "525", "light")
    cortex.password = "changed-on-cortex"  # login now becomes anonymous "default"
    with pytest.raises(HomeAssistantError, match="not permitted"):
        await hass.services.async_call("light", "turn_on", {"entity_id": entity_id}, blocking=True)


async def test_unavailable_when_cortex_goes_away(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    entity_id = entity_id_for(hass, entry, "76", "light")
    assert hass.states.get(entity_id).state == STATE_OFF
    await cortex.stop()
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_setup_retries_when_unreachable(hass: HomeAssistant, cortex) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=user_input(cortex, **{CONF_PORT: 1}))
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_diagnostics_redacts_credentials(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "secret" not in text
    assert "127.0.0.1" not in text
    assert diag["entry"][CONF_PASSWORD] == "**REDACTED**"
    assert diag["object_counts"]["Light"] == 21
    assert len(diag["supported"]) == 35
    assert len(diag["skipped"]) == 9
    assert any("Turn On" in line for line in diag["port_layouts"]["Light"])
