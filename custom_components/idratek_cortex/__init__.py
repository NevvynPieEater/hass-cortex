"""The Idratek Cortex integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CortexClient, CortexError
from .const import CONF_SSL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import CortexCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type CortexConfigEntry = ConfigEntry[CortexCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CortexConfigEntry) -> bool:
    """Set up Idratek Cortex from a config entry."""
    data = entry.data
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, False))
    client = CortexClient(
        session,
        data[CONF_HOST],
        data[CONF_PORT],
        data.get(CONF_USERNAME, ""),
        data.get(CONF_PASSWORD, ""),
        ssl=data.get(CONF_SSL, False),
    )
    coordinator = CortexCoordinator(hass, entry, client)
    try:
        await coordinator.async_discover()
    except CortexError as err:
        raise ConfigEntryNotReady(f"Cannot read objects from Cortex: {err}") from err
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_setup_buttons()
    entry.runtime_data = coordinator

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_hub")},
        name="Idratek Cortex",
        manufacturer="Idratek",
        model="Cortex",
        configuration_url=client.base_url,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def _async_reload_on_update(hass: HomeAssistant, entry: CortexConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CortexConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
