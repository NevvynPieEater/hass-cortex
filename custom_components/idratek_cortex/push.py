"""Receive pushed values from Cortex (Web API Client -> Home Assistant webhook).

A Cortex "Web API Client" item can call a URL when one of its connections is
triggered, with tags such as <Object.Port=?> replaced by the live value. Point
it at this webhook with three query parameters:

    object  the Cortex object id (or its exact name)
    port    the Cortex output port name (for example "Output")
    value   the port value, normally the tag <Object.Port=?>

The value updates the matching entity at once instead of waiting for the next
poll. For button panels, a press port going above 0 fires the button's event.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.core import HomeAssistant

from .const import BUTTON_EVENT_PORTS, DOMAIN

if TYPE_CHECKING:
    from . import CortexConfigEntry

_LOGGER = logging.getLogger(__name__)

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _clean(text: str) -> str:
    """Collapse the stray spaces Cortex leaves in names."""
    return " ".join(text.split()).casefold()


def parse_value(raw: str) -> float | None:
    """Return the first number in a pushed value (Cortex adds stray characters)."""
    match = _NUMBER.search(raw)
    return float(match.group()) if match else None


async def _params(request: web.Request) -> dict[str, Any]:
    """Merge query, form and JSON parameters."""
    params: dict[str, Any] = dict(request.query)
    if request.method == "POST" and request.can_read_body:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            body = None
        if isinstance(body, dict):
            params.update(body)
        else:
            try:
                params.update(dict(await request.post()))
            except (ValueError, UnicodeDecodeError):
                pass
    return params


def async_register(hass: HomeAssistant, entry: CortexConfigEntry, webhook_id: str) -> None:
    """Register the receiver for this entry."""

    async def handle(hass: HomeAssistant, _id: str, request: web.Request) -> web.Response:
        coordinator = entry.runtime_data
        params = await _params(request)
        wanted = str(params.get("object", "")).strip()
        port = " ".join(str(params.get("port", "")).split())
        raw = str(params.get("value", ""))
        value = parse_value(raw)
        if not wanted or not port or value is None:
            return web.Response(status=400, text="need object, port and a numeric value")

        obj = coordinator.objects.get(wanted) or next(
            (o for o in coordinator.objects.values() if _clean(o.name) == _clean(wanted)),
            None,
        )
        if obj is None:
            return web.Response(status=404, text=f"unknown object {wanted}")

        # Button press ports
        panel = coordinator.buttons.get(obj.id)
        buttons = coordinator.button_coordinator
        if panel and buttons is not None:
            for ports in panel.values():
                for event, name in ports.items():
                    if _clean(name) == _clean(port) and event in BUTTON_EVENT_PORTS:
                        buttons.async_push(obj.id, name, value > 0)
                        return web.Response(text="ok")

        item = coordinator.supported.get(obj.id)
        if item is None:
            return web.Response(status=404, text=f"{obj.name} is not supported")
        role = next(
            (r for r, name in item.state_ports.items() if _clean(name) == _clean(port)), None
        )
        if role is None:
            return web.Response(status=404, text=f"{port} is not a watched port of {obj.name}")
        coordinator.async_push(obj.id, role, f"{value:g}")
        return web.Response(text="ok")

    webhook.async_register(
        hass,
        DOMAIN,
        "Idratek Cortex",
        webhook_id,
        handle,
        local_only=True,
        allowed_methods=["GET", "POST"],
    )
    _LOGGER.debug("Cortex webhook registered")


def async_unregister(hass: HomeAssistant, webhook_id: str) -> None:
    """Remove the receiver."""
    webhook.async_unregister(hass, webhook_id)
