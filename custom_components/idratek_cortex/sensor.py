"""Sensor platform for Idratek Cortex (temperature, humidity, light level, HVAC set-points)."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import (
    TYPE_HUMIDITY,
    TYPE_HVAC,
    TYPE_LIGHT_LEVEL,
    TYPE_TEMPERATURE,
)
from .coordinator import CortexCoordinator, SupportedObject
from .entity import CortexEntity, to_float


@dataclass(frozen=True)
class SensorSpec:
    """How one port role becomes a sensor."""

    role: str
    name: str | None  # None = use the Cortex object name
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    precision: int | None = None
    enabled_default: bool = True
    first: bool = False  # first entity of an object keeps the plain unique id


SPECS: dict[str, tuple[SensorSpec, ...]] = {
    TYPE_TEMPERATURE: (
        SensorSpec(
            "state",
            None,
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            1,
            first=True,
        ),
    ),
    TYPE_HUMIDITY: (
        SensorSpec("state", None, SensorDeviceClass.HUMIDITY, PERCENTAGE, 0, first=True),
        SensorSpec(
            "dewpoint",
            "Dew point",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            1,
            enabled_default=False,
        ),
    ),
    # Unit/scale of the Cortex light level has not been confirmed: shown raw.
    TYPE_LIGHT_LEVEL: (SensorSpec("state", None, None, None, 1, first=True),),
    TYPE_HVAC: (
        SensorSpec(
            "heating_setpoint",
            "Heating set-point",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            1,
        ),
        SensorSpec(
            "cooling_setpoint",
            "Cooling set-point",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            1,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexSensor(coordinator, item, spec)
        for item in coordinator.supported.values()
        for spec in SPECS.get(item.obj.type, ())
    )


class CortexSensor(CortexEntity, SensorEntity):
    """A numeric Cortex reading."""

    def __init__(
        self, coordinator: CortexCoordinator, item: SupportedObject, spec: SensorSpec
    ) -> None:
        """Initialise."""
        super().__init__(coordinator, item, None if spec.first else spec.role)
        self._role = spec.role
        if spec.name:
            self._attr_name = f"{self._attr_name} {spec.name}"
        self._attr_device_class = spec.device_class
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_suggested_display_precision = spec.precision
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_registry_enabled_default = spec.enabled_default

    @property
    def native_value(self) -> float | None:
        """Return the reading."""
        return to_float(self.value)
