"""Sensor platform for Idratek Cortex (temperature)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import TYPE_TEMPERATURE
from .entity import CortexEntity, to_float


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex temperature sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexTemperature(coordinator, item)
        for item in coordinator.supported.values()
        if item.obj.type == TYPE_TEMPERATURE
    )


class CortexTemperature(CortexEntity, SensorEntity):
    """A Cortex temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        return to_float(self.values.get("state"))
