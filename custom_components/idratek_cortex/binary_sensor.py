"""Binary sensor platform for Idratek Cortex (doors, motion, presence, heating demand)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import (
    TYPE_BOILER,
    TYPE_DOOR,
    TYPE_FAN,
    TYPE_HEAT_ZONE,
    TYPE_HOUSE,
    TYPE_HVAC,
    TYPE_LIGHT_LEVEL,
    TYPE_MOTION,
)
from .coordinator import CortexCoordinator, SupportedObject
from .entity import CortexEntity, to_float


@dataclass(frozen=True)
class BinarySpec:
    """How one port role becomes a binary sensor."""

    role: str
    name: str | None  # None = use the Cortex object name; otherwise appended to it
    device_class: BinarySensorDeviceClass | None = None
    enabled_default: bool = True
    first: bool = False  # first entity of an object keeps the plain unique id
    attributes: tuple[str, ...] = ()  # extra roles shown as attributes
    replace_name: bool = False  # name replaces the Cortex object name


SPECS: dict[str, tuple[BinarySpec, ...]] = {
    # "Door output state": 100 is treated as open (see README).
    TYPE_DOOR: (BinarySpec("state", None, BinarySensorDeviceClass.DOOR, first=True, attributes=("fault",)),),
    TYPE_MOTION: (
        BinarySpec(
            "state", None, BinarySensorDeviceClass.MOTION, first=True, attributes=("long", "fault")
        ),
    ),
    # The property-wide presence state of the Cortex "House" object.
    TYPE_HOUSE: (
        BinarySpec(
            "state",
            "Presence",
            BinarySensorDeviceClass.OCCUPANCY,
            first=True,
            replace_name=True,
        ),
        BinarySpec("vacant", "Vacant mode", None, replace_name=True),
        BinarySpec("unoccupied_24h", "Unoccupied over 24 hours", None, replace_name=True),
    ),
    TYPE_LIGHT_LEVEL: (BinarySpec("dark", "Dark", None, replace_name=True),),
    TYPE_BOILER: (
        BinarySpec("state", None, BinarySensorDeviceClass.RUNNING, first=True),
        BinarySpec("demand", "Demand for extra heating", None),
    ),
    TYPE_HEAT_ZONE: (
        BinarySpec("state", None, BinarySensorDeviceClass.HEAT, first=True),
        BinarySpec("to_boiler", "Calling for boiler", None),
    ),
    TYPE_FAN: (BinarySpec("state", None, BinarySensorDeviceClass.RUNNING, first=True),),
    TYPE_HVAC: (
        BinarySpec("heating", "Heating", BinarySensorDeviceClass.HEAT),
        BinarySpec("cooling", "Cooling", BinarySensorDeviceClass.COLD),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexBinarySensor(coordinator, item, spec)
        for item in coordinator.supported.values()
        for spec in SPECS.get(item.obj.type, ())
    )


class CortexBinarySensor(CortexEntity, BinarySensorEntity):
    """An on/off Cortex output (0 = off, anything above 0 = on)."""

    def __init__(
        self, coordinator: CortexCoordinator, item: SupportedObject, spec: BinarySpec
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, item, None if spec.first else spec.role)
        self._role = spec.role
        self._extra = spec.attributes
        if spec.name:
            self._attr_name = (
                spec.name if spec.replace_name else f"{self._attr_name} {spec.name}"
            )
        self._attr_device_class = spec.device_class
        self._attr_entity_registry_enabled_default = spec.enabled_default

    @property
    def is_on(self) -> bool | None:
        """Return True if the output is on."""
        value = to_float(self.value)
        return None if value is None else value > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose related raw outputs such as a device fault flag."""
        return {f"cortex_{role}": self.values.get(role) for role in self._extra}
