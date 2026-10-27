"""Base entity for Idratek Cortex."""

from __future__ import annotations

import re

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CortexCoordinator, SupportedObject


def slugify_part(value: str) -> str:
    """Return a stable identifier fragment."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def entity_name(item: SupportedObject) -> str:
    """Return the entity name without repeating the room (device) name."""
    name = item.obj.name
    parent = item.obj.parent
    if parent and len(name) > len(parent) + 1 and name.lower().startswith(parent.lower() + " "):
        name = name[len(parent) + 1 :]
    return name[:1].upper() + name[1:]


class CortexEntity(CoordinatorEntity[CortexCoordinator]):
    """An entity backed by one Cortex object."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CortexCoordinator, item: SupportedObject) -> None:
        """Initialise."""
        super().__init__(coordinator)
        self._item = item
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{item.id}"
        self._attr_name = entity_name(item)
        parent = item.obj.parent or "Cortex"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_room_{slugify_part(parent)}")},
            name=parent,
            manufacturer="Idratek",
            model="Cortex group",
            via_device=(DOMAIN, f"{entry_id}_hub"),
        )

    @property
    def values(self) -> dict[str, str]:
        """Return the latest raw values for this object."""
        return (self.coordinator.data or {}).get(self._item.id, {})

    @property
    def available(self) -> bool:
        """Return True if the object was read successfully."""
        return super().available and self._item.id in (self.coordinator.data or {})


def to_float(value: str | None) -> float | None:
    """Parse a Cortex number."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
