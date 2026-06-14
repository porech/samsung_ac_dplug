"""The Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from samsung_dplug import SamsungAcClient, build_ssl_context

from .const import CONF_DUID, CONF_HOST, CONF_TOKEN, DOMAIN
from .coordinator import SamsungAcCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ssl_ctx = await hass.async_add_executor_job(build_ssl_context)
    client = SamsungAcClient(
        host=entry.data[CONF_HOST],
        token=entry.data[CONF_TOKEN],
        ssl_context=ssl_ctx,
        duid=entry.data.get(CONF_DUID),
    )
    coordinator = SamsungAcCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
