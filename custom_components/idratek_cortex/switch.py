"""Switch platform for Idratek Cortex (on/off loads such as sockets)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import TYPE_ALL_LIGHT, TYPE_ONOFF
from .entity import CortexEntity, to_float


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    for item in coordinator.supported.values():
        if item.obj.type == TYPE_ONOFF:
            entities.append(CortexSwitch(coordinator, item))
        elif item.obj.type == TYPE_ALL_LIGHT:
            entities.extend(
                CortexModeSwitch(coordinator, item, role, name, key)
                for role, name, key in ALL_LIGHT_SWITCHES
            )
    async_add_entities(entities)


# role, entity name, command prefix (<prefix>_on / <prefix>_off)
ALL_LIGHT_SWITCHES = (
    ("stealth", "Stealth mode", "stealth"),
    ("occupancy_enabled", "Occupancy simulation", "occupancy"),
)


class CortexSwitch(CortexEntity, SwitchEntity):
    """A Cortex on/off load."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    @property
    def is_on(self) -> bool | None:
        """Return True if the load is on."""
        value = to_float(self.values.get("state"))
        return None if value is None else value > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the load on."""
        await self.coordinator.async_command(self._item.id, "on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the load off."""
        await self.coordinator.async_command(self._item.id, "off")


class CortexModeSwitch(CortexEntity, SwitchEntity):
    """A house-wide mode on the All Light object (Stealth, occupancy simulation).

    The on and off commands are separate ports ("Enable" / "Disable") so the
    switch is idempotent; the state is read from the object's state output.
    """

    def __init__(self, coordinator, item, role: str, name: str, prefix: str) -> None:
        """Initialise."""
        super().__init__(coordinator, item, role)
        self._attr_name = name
        self._prefix = prefix

    @property
    def is_on(self) -> bool | None:
        """Return True if the mode is on."""
        value = to_float(self.value)
        return None if value is None else value > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Show whether occupancy simulation is running right now."""
        if self._role != "occupancy_enabled":
            return None
        active = to_float(self.values.get("occupancy_active"))
        return None if active is None else {"active": active > 0}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the mode on."""
        await self.coordinator.async_command(self._item.id, f"{self._prefix}_on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the mode off."""
        await self.coordinator.async_command(self._item.id, f"{self._prefix}_off")
