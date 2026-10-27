"""Cover platform for Idratek Cortex (motorised blinds).

Meaning of the Cortex values (confirmed by the owner for a partly open blind):
"State (Output)" is 100 when the blind is open (at any amount) and the analogue
"Set State (Output) Analogue" is how far open it is, in percent (100 = fully
open). Closed is assumed to be State 0 / position 0 - not yet seen live.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CortexConfigEntry
from .const import BLIND_REFRESH_DELAYS, TYPE_BLIND
from .entity import CortexEntity, to_float


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CortexConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cortex blinds."""
    coordinator = entry.runtime_data
    async_add_entities(
        CortexBlind(coordinator, item)
        for item in coordinator.supported.values()
        if item.obj.type == TYPE_BLIND
    )


class CortexBlind(CortexEntity, CoverEntity):
    """A Cortex motor-controlled blind."""

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    @property
    def current_cover_position(self) -> int | None:
        """Return how far open the blind is (0-100)."""
        value = to_float(self.values.get("position"))
        return None if value is None else max(0, min(100, round(value)))

    @property
    def is_closed(self) -> bool | None:
        """Return True if the blind is closed (State 0)."""
        state = to_float(self.values.get("state"))
        return None if state is None else state == 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose raw Cortex values."""
        values = self.values
        return {
            "cortex_state": values.get("state"),
            "cortex_position": values.get("position"),
            "cortex_busy": values.get("busy"),
        }

    async def _send(self, key: str) -> None:
        await self.coordinator.async_command(self._item.id, key)
        self.coordinator.async_schedule_refreshes(self._item.id, BLIND_REFRESH_DELAYS)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the blind."""
        await self._send("open")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the blind."""
        await self._send("close")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the blind."""
        await self._send("stop")
