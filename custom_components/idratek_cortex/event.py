"""Event entities for Cortex button panels."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CortexConfigEntry
from .buttons import ButtonCoordinator, press_key
from .coordinator import SupportedObject
from .entity import entity_name, room_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one event entity per Cortex button."""
    coordinator = entry.runtime_data
    buttons = coordinator.button_coordinator
    if buttons is None:
        return
    async_add_entities(
        CortexButtonEvent(buttons, coordinator.objects[obj_id], number, ports)
        for obj_id, panel in coordinator.buttons.items()
        for number, ports in panel.items()
    )


class CortexButtonEvent(CoordinatorEntity[ButtonCoordinator], EventEntity):
    """One button of a Cortex panel (single click, double click, long press)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ButtonCoordinator, obj, number: int, ports: dict[str, str]) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._object_id = obj.id
        self._ports = ports
        self._attr_event_types = list(ports)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{obj.id}_button_{number}"
        self._attr_name = f"{entity_name(SupportedObject(obj, {}))} {number}"
        self._attr_device_info = room_device_info(entry_id, obj.parent)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an event for every press type that just rose."""
        for event_type, port in self._ports.items():
            if press_key(self._object_id, port) in self.coordinator.pressed:
                self._trigger_event(event_type)
                self.async_write_ha_state()
        super()._handle_coordinator_update()
