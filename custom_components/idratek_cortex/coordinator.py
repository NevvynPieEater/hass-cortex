"""Data coordinator for Idratek Cortex."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CortexApiError,
    CortexClient,
    CortexConnectionError,
    CortexError,
    CortexObject,
    CortexPort,
)
from .const import (
    COMMAND_PORTS,
    COMMAND_SETTLE_DELAY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STATE_PORTS,
    TYPE_TEMPERATURE,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

# Coordinator data: object id -> role -> raw text value.
CortexData = dict[str, dict[str, str]]


@dataclass
class SupportedObject:
    """An object that becomes a Home Assistant entity."""

    obj: CortexObject
    state_ports: dict[str, str]  # role -> port name
    commands: dict[str, str] = field(default_factory=dict)  # key -> port name

    @property
    def id(self) -> str:
        """Return the Cortex object id."""
        return self.obj.id


def find_temperature_port(ports: dict[str, CortexPort]) -> str | None:
    """Choose the port holding a temperature reading.

    The port layout of Temperature objects has not been captured from a real
    system yet (the test user was not permitted to read them), so this is a
    conservative heuristic: an output port with "temp" in its name, otherwise
    the only non-icon value output.
    """
    outputs = [
        p for p in ports.values() if p.direction in ("Out", "ValueOut") and "icon" not in p.name.lower()
    ]
    named = [p for p in outputs if "temp" in p.name.lower()]
    if named:
        return named[0].name
    value_outputs = [p for p in outputs if p.direction == "ValueOut"]
    if len(value_outputs) == 1:
        return value_outputs[0].name
    return None


class CortexCoordinator(DataUpdateCoordinator[CortexData]):
    """Discover Cortex objects and poll their state."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: CortexClient) -> None:
        """Initialise."""
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.objects: dict[str, CortexObject] = {}
        self.supported: dict[str, SupportedObject] = {}
        self.skipped: dict[str, str] = {}  # object id -> reason
        self.errors: dict[str, str] = {}  # object id -> last read error
        self._timers: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------ discovery

    async def async_discover(self) -> None:
        """Read the object list and each relevant object's port list."""
        objects = await self.client.list_objects()
        self.objects = {o.id: o for o in objects}
        self.supported = {}
        self.skipped = {}

        wanted = [
            o for o in objects if o.type in STATE_PORTS or o.type == TYPE_TEMPERATURE
        ]

        async def load(obj: CortexObject) -> None:
            try:
                obj.ports = await self.client.list_ports(obj)
            except CortexApiError as err:
                self.skipped[obj.id] = "no_permission" if err.permission else f"api_{err.code}"
            # CortexConnectionError propagates out of gather and aborts setup.

        await asyncio.gather(*(load(o) for o in wanted))

        for obj in wanted:
            if obj.id in self.skipped:
                continue
            if obj.type == TYPE_TEMPERATURE:
                port = find_temperature_port(obj.ports)
                if port is None:
                    self.skipped[obj.id] = "no_temperature_port"
                    continue
                self.supported[obj.id] = SupportedObject(obj, {"state": port})
                continue
            state_ports = STATE_PORTS[obj.type]
            commands = COMMAND_PORTS[obj.type]
            missing = [p for p in (*state_ports.values(), *commands.values()) if p not in obj.ports]
            if missing:
                self.skipped[obj.id] = f"missing_port:{missing[0]}"
                continue
            self.supported[obj.id] = SupportedObject(obj, dict(state_ports), dict(commands))

        for obj_id, reason in self.skipped.items():
            _LOGGER.info(
                "Skipping Cortex object %s (%s): %s",
                obj_id,
                self.objects[obj_id].name,
                reason,
            )

    # ------------------------------------------------------------------- polling

    async def _read_object(self, item: SupportedObject) -> dict[str, str]:
        """Read all state ports of one object."""
        roles = list(item.state_ports)
        values = await asyncio.gather(
            *(self.client.read_port(item.id, item.state_ports[r]) for r in roles)
        )
        return dict(zip(roles, values, strict=True))

    async def _async_update_data(self) -> CortexData:
        """Poll every supported object."""
        items = list(self.supported.values())
        results = await asyncio.gather(
            *(self._read_object(i) for i in items), return_exceptions=True
        )
        data: CortexData = {}
        connection_errors = 0
        for item, result in zip(items, results, strict=True):
            if isinstance(result, CortexConnectionError):
                connection_errors += 1
                self.errors[item.id] = str(result)
            elif isinstance(result, CortexError):
                self.errors[item.id] = str(result)
            elif isinstance(result, BaseException):
                raise result
            else:
                data[item.id] = result
                self.errors.pop(item.id, None)
        if items and connection_errors == len(items):
            raise UpdateFailed("Cannot reach the Cortex web server")
        return data

    async def async_refresh_object(self, object_id: str) -> None:
        """Refresh a single object and publish the result."""
        item = self.supported.get(object_id)
        if item is None:
            return
        try:
            values = await self._read_object(item)
        except CortexError as err:
            self.errors[object_id] = str(err)
            return
        self.errors.pop(object_id, None)
        self.async_set_updated_data({**(self.data or {}), object_id: values})

    # ------------------------------------------------------------------ commands

    async def async_command(self, object_id: str, key: str) -> None:
        """Send a command to an object and refresh its state."""
        item = self.supported[object_id]
        action = item.commands[key]
        try:
            await self.client.command(object_id, action)
        except CortexApiError as err:
            raise HomeAssistantError(
                f"Cortex refused '{action}' for {item.obj.name}: {err.message}"
            ) from err
        except CortexError as err:
            raise HomeAssistantError(
                f"Could not send '{action}' to {item.obj.name}: {err}"
            ) from err
        await asyncio.sleep(COMMAND_SETTLE_DELAY)
        await self.async_refresh_object(object_id)

    @callback
    def async_schedule_refreshes(self, object_id: str, delays: tuple[int, ...]) -> None:
        """Read an object again after the given delays (for slow movers like blinds)."""
        for delay in delays:

            async def _refresh(_now, object_id: str = object_id) -> None:
                await self.async_refresh_object(object_id)

            self._timers.append(async_call_later(self.hass, delay, _refresh))

    async def async_shutdown(self) -> None:
        """Cancel timers on unload."""
        for cancel in self._timers:
            cancel()
        self._timers.clear()
        await super().async_shutdown()
