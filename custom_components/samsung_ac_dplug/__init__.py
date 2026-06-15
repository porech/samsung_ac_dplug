"""The Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from samsung_dplug import SamsungAcClient, SamsungAcStream, build_ssl_context

from .const import (
    CONF_DUID,
    CONF_HOST,
    CONF_LIVE_UPDATES,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_LIVE_UPDATES,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import SamsungAcConfigEntry, SamsungAcCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: SamsungAcConfigEntry) -> bool:
    ssl_ctx = await hass.async_add_executor_job(build_ssl_context)
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    duid = entry.data.get(CONF_DUID)
    live = entry.options.get(CONF_LIVE_UPDATES, DEFAULT_LIVE_UPDATES)
    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    if live:
        stream = SamsungAcStream(
            host, token, ssl_ctx, duid=duid, fallback_interval=interval, logger=_LOGGER
        )
        coordinator = SamsungAcCoordinator(hass, entry, stream=stream, interval=interval)
        stream.set_on_update(coordinator.handle_push)
        await stream.start()
        if stream.auth_failed:
            await stream.stop()
            raise ConfigEntryAuthFailed("Token rejected")
        if not stream.connected:
            await stream.stop()
            raise ConfigEntryNotReady(f"Cannot reach {host}")
        coordinator.async_set_updated_data(stream.state)
    else:
        client = SamsungAcClient(host=host, token=token, ssl_context=ssl_ctx, duid=duid)
        coordinator = SamsungAcCoordinator(hass, entry, client=client, interval=interval)
        await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SamsungAcConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and entry.runtime_data.stream is not None:
        await entry.runtime_data.stream.stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: SamsungAcConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
