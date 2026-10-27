"""Diagnostics for Idratek Cortex."""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import CortexConfigEntry

TO_REDACT = {CONF_HOST, CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CortexConfigEntry
) -> dict[str, Any]:
    """Return diagnostics (credentials and address redacted).

    Object names and port names are included on purpose: they are needed to
    fix port mapping, and this file is only produced when the user asks for it.
    """
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "object_counts": dict(Counter(o.type for o in coordinator.objects.values())),
        "supported": [
            {
                "id": i.id,
                "name": i.obj.name,
                "type": i.obj.type,
                "parent": i.obj.parent,
                "state_ports": i.state_ports,
                "commands": i.commands,
                "values": (coordinator.data or {}).get(i.id),
            }
            for i in coordinator.supported.values()
        ],
        "skipped": {
            obj_id: {
                "name": coordinator.objects[obj_id].name,
                "type": coordinator.objects[obj_id].type,
                "reason": reason,
            }
            for obj_id, reason in coordinator.skipped.items()
        },
        "read_errors": coordinator.errors,
        # Port layouts per type (first object of each type), to confirm mappings.
        "port_layouts": {
            type_: [f"{p.index}: {p.name} [{p.direction}]" for p in obj.ports.values()]
            for type_, obj in {
                o.type: o for o in reversed(list(coordinator.objects.values())) if o.ports
            }.items()
        },
    }
