"""Switch platform for Idratek Cortex (on/off loads such as sockets)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import TYPE_ONOFF
from .entity import CortexEntity, to_float


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexSwitch(coordinator, item)
        for item in coordinator.supported.values()
        if item.obj.type == TYPE_ONOFF
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
