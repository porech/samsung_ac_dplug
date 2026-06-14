"""DataUpdateCoordinator for the Samsung AC (DPLUG/2878) integration.

Two modes:
- polling: short-lived connections (more resilient), refresh every scan_interval.
- live: one persistent connection (SamsungAcStream) pushing updates; the stream's
  watchdog polls every scan_interval as a fallback/keepalive.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from samsung_dplug import SamsungAcClient, SamsungAcError, SamsungAcStream

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SamsungAcCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        client: SamsungAcClient | None = None,
        stream: SamsungAcStream | None = None,
        interval: int = 30,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data.get('host')}",
            # live mode is push-driven -> no periodic polling by the coordinator
            update_interval=None if stream else timedelta(seconds=interval),
            always_update=False,
        )
        self.client = client
        self.stream = stream
        self.entry = entry

    async def _async_update_data(self) -> dict:
        if self.stream is not None:
            # push mode: coordinator does not poll; return last known state.
            return self.data or self.stream.state
        try:
            return await self.client.async_get_state()
        except SamsungAcError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def handle_push(self, state: dict) -> None:
        """Called by the stream when new state arrives."""
        self.async_set_updated_data(state)

    async def async_set(self, attr: str, value: str) -> None:
        if self.stream is not None:
            await self.stream.async_set(attr, value)
            # state will arrive via push; no manual refresh needed
        else:
            await self.client.async_set(attr, value)
            await self.async_request_refresh()
