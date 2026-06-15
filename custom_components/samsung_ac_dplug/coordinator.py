"""DataUpdateCoordinator for the Samsung AC (DPLUG/2878) integration.

Two modes:
- polling: short-lived connections (more resilient), refresh every scan_interval.
- live: one persistent connection (SamsungAcStream) pushing updates; the stream's
  watchdog polls every scan_interval as a fallback/keepalive.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from samsung_dplug import AuthError, SamsungAcClient, SamsungAcError, SamsungAcStream

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SamsungAcConfigEntry = ConfigEntry[SamsungAcCoordinator]


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
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SamsungAcError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def handle_push(self, state: dict) -> None:
        """Called by the stream when new state arrives."""
        self.async_set_updated_data(state)

    @property
    def device_clock(self):
        """The unit's internal clock (UTC datetime) from the last auth, or None."""
        return self.stream.start_from if self.stream is not None else self.client.start_from

    async def async_set(self, attr: str, value: str) -> None:
        if self.stream is not None:
            # stream.async_set waits for the device to confirm via push
            await self.stream.async_set(attr, value)
            return
        # polling: send, then re-poll once per second for up to 5s until applied,
        # so the entity reflects the confirmed value immediately rather than at
        # the next scheduled poll.
        await self.client.async_set(attr, value)
        loop = asyncio.get_running_loop()
        end = loop.time() + 5
        data = await self.client.async_get_state()
        while str(data.get(attr)) != str(value) and loop.time() < end:
            await asyncio.sleep(1)
            data = await self.client.async_get_state()
        self.async_set_updated_data(data)
