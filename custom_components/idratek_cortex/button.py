"""Button platform for Idratek Cortex (the All Light "Good Night" action)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import TYPE_ALL_LIGHT
from .entity import CortexEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexGoodNightButton(coordinator, item, "good_night")
        for item in coordinator.supported.values()
        if item.obj.type == TYPE_ALL_LIGHT
    )


class CortexGoodNightButton(CortexEntity, ButtonEntity):
    """Press the All Light "Good Night" input."""

    _attr_name = "Good night"
    _attr_icon = "mdi:weather-night"

    async def async_press(self) -> None:
        """Send Good Night to Cortex."""
        await self.coordinator.async_command(self._item.id, "good_night")
