"""Light platform for Idratek Cortex."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import TYPE_LIGHT
from .coordinator import CortexCoordinator, SupportedObject
from .entity import CortexEntity, to_float


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex lights."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexLight(coordinator, item)
        for item in coordinator.supported.values()
        if item.obj.type == TYPE_LIGHT
    )


class CortexLight(CortexEntity, LightEntity):
    """An on/off Cortex light (no dimming port was found on these objects)."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: CortexCoordinator, item: SupportedObject) -> None:
        """Initialise."""
        super().__init__(coordinator, item)

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        value = to_float(self.values.get("state"))
        return None if value is None else value > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.coordinator.async_command(self._item.id, "on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.async_command(self._item.id, "off")
