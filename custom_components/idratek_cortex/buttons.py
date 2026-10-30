"""Fast poller for Cortex button panels.

Button outputs are momentary: they rise to 100 for a few seconds and fall back
to 0. The main coordinator polls every 30 seconds, which would almost never see
a press, so button ports are read by their own, quicker coordinator and a press
is the rising edge of a port.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CortexClient, CortexConnectionError, CortexError
from .const import CONF_BUTTON_INTERVAL, DEFAULT_BUTTON_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


def press_key(object_id: str, port: str) -> str:
    """Return the key used for one button port."""
    return f"{object_id}|{port}"


class ButtonCoordinator(DataUpdateCoordinator[dict[str, bool]]):
    """Read every button port and report rising edges."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CortexClient,
        ports: list[tuple[str, str]],
    ) -> None:
        """Initialise with the (object id, port name) pairs to watch."""
        interval = entry.options.get(CONF_BUTTON_INTERVAL, DEFAULT_BUTTON_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_buttons",
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.ports = ports
        self.pressed: set[str] = set()  # ports that rose in the latest update
        self._primed = False

    async def _async_update_data(self) -> dict[str, bool]:
        """Read all button ports; a press is a port that was low and is now high."""
        results = await asyncio.gather(
            *(self.client.read_port(obj, port) for obj, port in self.ports),
            return_exceptions=True,
        )
        previous = self.data or {}
        high: dict[str, bool] = {}
        failures = 0
        for (obj, port), result in zip(self.ports, results, strict=True):
            key = press_key(obj, port)
            if isinstance(result, CortexConnectionError):
                failures += 1
                high[key] = previous.get(key, False)
            elif isinstance(result, CortexError):
                high[key] = previous.get(key, False)
            elif isinstance(result, BaseException):
                raise result
            else:
                try:
                    high[key] = float(result) > 0
                except ValueError:
                    high[key] = previous.get(key, False)
        if self.ports and failures == len(self.ports):
            raise UpdateFailed("Cannot reach the Cortex web server")
        # The first read only records the starting state, so a button that is
        # already high when Home Assistant starts does not fire an event.
        self.pressed = (
            {k for k, v in high.items() if v and not previous.get(k, False)}
            if self._primed
            else set()
        )
        self._primed = True
        return high
