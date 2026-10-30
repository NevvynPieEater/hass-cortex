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
    # 18 temperatures + humidity + light level + 2 HVAC set-points
    # (the dew point sensor is disabled by default)
    assert len(hass.states.async_all("sensor")) == 22
    # 6 doors, 1 motion, 3 property presence, 1 dark, 4 boiler, 2 heat zone, 1 fan, 2 HVAC,
    # 11 room occupancy (the delayed-occupancy sensors are disabled by default)
    assert len(hass.states.async_all("binary_sensor")) == 32
    coordinator = entry.runtime_data
    assert not coordinator.skipped


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


async def test_temperature_sensors(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    state = hass.states.get(entity_id_for(hass, entry, "82", "sensor"))
    assert float(state.state) == pytest.approx(19.8, abs=0.05)
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["friendly_name"] == "Kitchen Temperature"
    # one of the sensors that were refused before the user was given access
    outdoors = hass.states.get(entity_id_for(hass, entry, "855", "sensor"))
    assert float(outdoors.state) == pytest.approx(9.8, abs=0.05)


async def test_temperature_refused_is_skipped(hass: HomeAssistant, cortex) -> None:
    cortex.blocked_types = {"Temperature"}
    entry = await setup_entry(hass, cortex)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_82") is None
    assert len(hass.states.async_all("sensor")) == 4  # humidity, light level, 2 HVAC set-points
    assert sum(r == "no_permission" for r in entry.runtime_data.skipped.values()) == 18


async def test_humidity_light_level_and_hvac(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    humidity = hass.states.get(entity_id_for(hass, entry, "83", "sensor"))
    assert float(humidity.state) == 59
    assert humidity.attributes["device_class"] == "humidity"
    registry = er.async_get(hass)
    dew = registry.async_get(
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_83_dewpoint")
    )
    assert dew.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    level = hass.states.get(entity_id_for(hass, entry, "88", "sensor"))
    assert level.state == "0.0"
    heating = hass.states.get(
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_615_heating_setpoint")
    )
    assert float(heating.state) == 12
    assert heating.attributes["friendly_name"] == "Lounge HVAC Heating set-point"


async def test_doors_motion_and_presence(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    french = hass.states.get(entity_id_for(hass, entry, "1107", "binary_sensor"))
    assert french.state == STATE_ON  # Door output state 100
    assert french.attributes["device_class"] == "door"
    assert french.attributes["friendly_name"] == "Dining room French door"
    assert french.attributes["cortex_fault"] == "0"
    front = hass.states.get(entity_id_for(hass, entry, "336", "binary_sensor"))
    assert front.state == STATE_OFF
    assert front.attributes["friendly_name"] == "Hall Front Door"
    # double space in "Dining room Door  3" is collapsed
    door3 = hass.states.get(entity_id_for(hass, entry, "1099", "binary_sensor"))
    assert door3.attributes["friendly_name"] == "Dining room Door 3"

    motion = hass.states.get(entity_id_for(hass, entry, "85", "binary_sensor"))
    assert motion.state == STATE_OFF
    assert motion.attributes["device_class"] == "motion"

    # The "House" object shares the device of the property's outdoor lights.
    presence = hass.states.get(entity_id_for(hass, entry, "20", "binary_sensor"))
    assert presence.state == STATE_ON
    assert presence.attributes["device_class"] == "occupancy"
    assert presence.attributes["friendly_name"] == "Outside Presence"
    light = er.async_get(hass).async_get(entity_id_for(hass, entry, "550", "light"))
    house = er.async_get(hass).async_get(presence.entity_id)
    assert light.device_id == house.device_id


async def test_room_occupancy(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    registry = er.async_get(hass)
    bedroom = hass.states.get(entity_id_for(hass, entry, "33", "binary_sensor"))
    assert bedroom.state == STATE_ON
    assert bedroom.attributes["device_class"] == "occupancy"
    assert bedroom.attributes["friendly_name"] == "Bedroom 1 Occupancy"
    kitchen = hass.states.get(entity_id_for(hass, entry, "25", "binary_sensor"))
    assert kitchen.state == STATE_OFF
    # shares a device with the room's lights, not a "Downstairs" device
    light = registry.async_get(entity_id_for(hass, entry, "76", "light"))
    assert registry.async_get(kitchen.entity_id).device_id == light.device_id
    delayed = registry.async_get(
        registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_25_delayed")
    )
    assert delayed.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_boiler_fan_and_heat_zone(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    for object_id in ("452", "617", "946", "470"):
        assert hass.states.get(entity_id_for(hass, entry, object_id, "binary_sensor")).state == STATE_OFF


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
    assert len(diag["supported"]) == 35 + 18 + 1 + 6 + 1 + 1 + 1 + 2 + 1 + 1 + 1 + 11 + 1
    assert diag["skipped"] == {}
    assert any("Turn On" in line for line in diag["port_layouts"]["Light"])


# --------------------------------------------------------------- button panels


def button_event_id(hass: HomeAssistant, entry, number: int) -> str:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("event", DOMAIN, f"{entry.entry_id}_81_button_{number}")
    assert entity_id, f"no event entity for button {number}"
    return entity_id


async def test_button_events_are_created(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    assert len(hass.states.async_all("event")) == 12
    state = hass.states.get(button_event_id(hass, entry, 4))
    assert state.attributes["event_types"] == ["single_click", "double_click", "long_press"]
    assert state.attributes["friendly_name"] == "Kitchen Buttons 4"
    # on the Kitchen device, with the lights
    registry = er.async_get(hass)
    light = registry.async_get(entity_id_for(hass, entry, "76", "light"))
    assert registry.async_get(state.entity_id).device_id == light.device_id


async def test_button_press_fires_once(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    buttons = entry.runtime_data.button_coordinator
    entity_id = button_event_id(hass, entry, 4)
    assert hass.states.get(entity_id).attributes.get("event_type") is None

    cortex.state["81"]["Single Click Button 4"] = "100"
    await buttons.async_refresh()
    await hass.async_block_till_done()
    first = hass.states.get(entity_id)
    assert first.attributes["event_type"] == "single_click"

    # Still held high on the next poll: no second event.
    await buttons.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == first.state

    # Released, then a long press on the same button.
    cortex.state["81"]["Single Click Button 4"] = "0"
    await buttons.async_refresh()
    cortex.state["81"]["Long Press Button 4"] = "100"
    await buttons.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["event_type"] == "long_press"
    # Other buttons are untouched.
    assert hass.states.get(button_event_id(hass, entry, 5)).attributes.get("event_type") is None


async def test_button_already_high_at_start_is_ignored(hass: HomeAssistant, cortex) -> None:
    cortex.state["81"]["Double Click Button 2"] = "100"
    entry = await setup_entry(hass, cortex)
    assert hass.states.get(button_event_id(hass, entry, 2)).attributes.get("event_type") is None


async def test_button_interval_option(hass: HomeAssistant, cortex) -> None:
    entry = await setup_entry(hass, cortex)
    assert entry.runtime_data.button_coordinator.update_interval.total_seconds() == 2
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 45, "button_interval": 1}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["button_interval"] == 1
