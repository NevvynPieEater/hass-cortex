"""Config flow for Idratek Cortex."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import CortexApiError, CortexClient, CortexConnectionError
from .const import (
    COMMAND_PORTS,
    CONF_BUTTON_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_PORT,
    DEFAULT_BUTTON_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_BUTTON_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_BUTTON_INTERVAL,
    MIN_SCAN_INTERVAL,
)

# How many controllable objects to probe when checking the login.
_PROBE_COUNT = 5


class CannotConnect(Exception):
    """Cortex unreachable or unusable reply."""


class NoPermission(Exception):
    """The user is not permitted to access any controllable object."""


def _user_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_SSL, default=defaults.get(CONF_SSL, False)): bool,
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)): bool,
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> int:
    """Check the connection and login. Returns the number of objects found.

    Cortex does not challenge for credentials: a wrong login simply gets the
    anonymous "default" user, which can list objects but is refused on the
    objects themselves. So the login is checked by reading a few controllable
    objects.
    """
    client = CortexClient(
        async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, False)),
        data[CONF_HOST],
        data[CONF_PORT],
        data.get(CONF_USERNAME, ""),
        data.get(CONF_PASSWORD, ""),
        ssl=data.get(CONF_SSL, False),
    )
    try:
        objects = await client.list_objects()
    except (CortexConnectionError, CortexApiError) as err:
        raise CannotConnect from err
    if not objects:
        raise CannotConnect

    probes = [o for o in objects if o.type in COMMAND_PORTS][:_PROBE_COUNT]
    if not probes:
        return len(objects)
    permitted = False
    for obj in probes:
        try:
            await client.list_ports(obj)
        except CortexApiError as err:
            if err.permission:
                continue
            raise CannotConnect from err
        except CortexConnectionError as err:
            raise CannotConnect from err
        permitted = True
        break
    if not permitted:
        raise NoPermission
    return len(objects)


class CortexConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Idratek Cortex."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return CortexOptionsFlow()

    async def _async_handle(
        self, user_input: dict[str, Any] | None, step_id: str, defaults: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip()}
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except NoPermission:
                errors["base"] = "no_permission"
            else:
                return errors, user_input
        return errors, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors, valid = await self._async_handle(user_input, "user", {})
        if valid is not None:
            await self.async_set_unique_id(f"{valid[CONF_HOST]}:{valid[CONF_PORT]}".lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=f"Idratek Cortex ({valid[CONF_HOST]})", data=valid)
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or login without losing entities."""
        entry = self._get_reconfigure_entry()
        errors, valid = await self._async_handle(user_input, "reconfigure", dict(entry.data))
        if valid is not None:
            return self.async_update_reload_and_abort(
                entry,
                unique_id=f"{valid[CONF_HOST]}:{valid[CONF_PORT]}".lower(),
                data_updates=valid,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or dict(entry.data)),
            errors=errors,
        )


class CortexOptionsFlow(OptionsFlow):
    """Options: polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_BUTTON_INTERVAL: int(user_input[CONF_BUTTON_INTERVAL]),
                }
            )
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_buttons = self.config_entry.options.get(
            CONF_BUTTON_INTERVAL, DEFAULT_BUTTON_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_BUTTON_INTERVAL, default=current_buttons): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_BUTTON_INTERVAL,
                        max=MAX_BUTTON_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=current): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
