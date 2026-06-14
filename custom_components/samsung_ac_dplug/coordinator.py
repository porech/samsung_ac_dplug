"""DataUpdateCoordinator for the Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from samsung_dplug import SamsungAcClient, SamsungAcError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


class SamsungAcCoordinator(DataUpdateCoordinator[dict]):
    """Polls the AC for its full DeviceState."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SamsungAcClient):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data.get('host')}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_get_state()
        except SamsungAcError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set(self, attr: str, value: str) -> None:
        """Send a control command then refresh state."""
        await self.client.async_set(attr, value)
        await self.async_request_refresh()
