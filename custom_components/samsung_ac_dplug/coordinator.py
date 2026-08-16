"""DataUpdateCoordinator for the Samsung AC (DPLUG/2878) integration.

Two modes:
- polling: short-lived connections (more resilient), refresh every scan_interval.
- live: one persistent connection (SamsungAcStream) pushing updates; the stream's
  watchdog polls every scan_interval as a fallback/keepalive.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
import datetime
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from samsung_dplug import (
    AuthError,
    PowerUsageEntry,
    SamsungAcClient,
    SamsungAcError,
    SamsungAcStream,
    Schedule,
)

from .const import ATTR_OPTIONCODE, DOMAIN, OPTION_USAGE

_LOGGER = logging.getLogger(__name__)

type SamsungAcConfigEntry = ConfigEntry[SamsungAcCoordinator]


class SamsungAcCoordinator(DataUpdateCoordinator[dict[str, str]]):
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
        # On-device schedules (cached; refreshed on demand and after mutations).
        self.schedules: list[Schedule] = []

    async def _async_update_data(self) -> dict[str, str]:
        if self.stream is not None:
            # push mode: coordinator does not poll; return last known state.
            return self.data or self.stream.state
        assert self.client is not None
        try:
            return await self.client.async_get_state()
        except AuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SamsungAcError as err:
            raise UpdateFailed(str(err)) from err

    @callback
    def handle_push(self, state: dict[str, str]) -> None:
        """Called by the stream when new state arrives."""
        self.async_set_updated_data(state)

    @callback
    def handle_availability(self, connected: bool) -> None:
        """Called by the stream when the live connection goes up or down."""
        host = self.entry.data.get("host")
        if connected:
            _LOGGER.info("Reconnected to Samsung AC at %s", host)
        else:
            _LOGGER.warning("Lost connection to Samsung AC at %s; entities are unavailable", host)
        self.async_update_listeners()

    @property
    def device_clock(self) -> datetime.datetime | None:
        """The unit's internal clock (UTC datetime) from the last auth, or None."""
        if self.stream is not None:
            return self.stream.start_from
        assert self.client is not None
        return self.client.start_from

    # -- on-device scheduling -----------------------------------------------
    @property
    def _api(self) -> SamsungAcStream | SamsungAcClient:
        """Whichever connection is active (stream in live mode, else client)."""
        api = self.stream if self.stream is not None else self.client
        assert api is not None
        return api

    @property
    def is_legacy_drc(self) -> bool:
        """Whether the connected unit uses the legacy DRC-1.00 protocol."""
        return getattr(self._api, "greeting", None) == "DRC-1.00"

    @property
    def _tz(self) -> datetime.tzinfo:
        """Home Assistant's configured timezone, for local<->UTC conversion."""
        return dt_util.DEFAULT_TIME_ZONE

    async def async_refresh_schedules(self) -> list[Schedule]:
        """Fetch the schedules stored on the unit and cache them (local time)."""
        self.schedules = await self._api.async_get_schedules(tz=self._tz)
        self.async_update_listeners()
        return self.schedules

    async def async_set_schedule(self, sched: Schedule) -> None:
        await self._api.async_set_schedule(sched, tz=self._tz)
        await self.async_refresh_schedules()

    async def async_delete_schedule(self, schedule_id: str) -> None:
        await self._api.async_delete_schedule(schedule_id)
        await self.async_refresh_schedules()

    # -- energy metering ----------------------------------------------------
    @property
    def usage_supported(self) -> bool:
        """Whether the unit meters cumulative energy (AC_ADD2_OPTIONCODE usage bit)."""
        oc = (self.data or {}).get(ATTR_OPTIONCODE)
        return bool(oc and oc.lstrip("-").isdigit() and int(oc) & OPTION_USAGE)

    # -- extra device commands (power usage/logging, nickname, region) --
    async def async_get_power_usage(
        self, date_from: datetime.datetime, date_to: datetime.datetime, unit: str
    ) -> list[PowerUsageEntry]:
        return await self._api.async_get_power_usage(date_from, date_to, unit, tz=self._tz)

    async def async_set_power_logging(self, enable: bool) -> None:
        await self._api.async_set_power_logging(enable)

    async def async_reset_power_logging(self) -> None:
        await self._api.async_reset_power_logging()

    async def async_set_nickname(self, nickname: str) -> None:
        await self._api.async_set_nickname(nickname)

    async def async_get_region_code(self) -> str | None:
        return await self._api.async_get_region_code()

    async def async_set_region_code(self, code: str) -> None:
        await self._api.async_set_region_code(code)

    async def async_power_debug(self) -> dict[str, Any]:
        """Read the raw power-metering values (for diagnosing metering support).

        Returns the relevant DeviceState attributes as-is plus a live
        GetPowerLoggingMode and a short GetPowerUsage sample, so a user can share
        a test reading (e.g. whether AC_ADD2_USEDWATT is a real live power value).
        """
        state = self.data or {}
        oc = state.get(ATTR_OPTIONCODE)
        usage_bit = bool(int(oc) & OPTION_USAGE) if oc and oc.lstrip("-").isdigit() else None
        raw = {
            k: state.get(k)
            for k in (
                "AC_ADD2_OPTIONCODE", "AC_ADD2_USEDWATT", "AC_ADD2_USEDPOWER",
                "AC_ADD2_USEDTIME", "AC_ADD_SETKWH", "AC_ADD2_CLEAR_POWERTIME",
            )
        }
        result: dict[str, Any] = {"device_state": raw, "usage_supported": usage_bit}
        try:
            result["logging_mode"] = await self._api.async_get_power_logging_mode()
        except SamsungAcError as err:
            result["logging_mode"] = f"error: {err}"
        end = dt_util.now()
        try:
            entries = await self._api.async_get_power_usage(
                end - timedelta(hours=3), end, "Hour", tz=self._tz
            )
            result["power_usage_sample"] = [
                {"time": e.time.isoformat(), "kwh": e.power_kwh, "hours": e.hours} for e in entries
            ]
        except SamsungAcError as err:
            result["power_usage_sample"] = f"error: {err}"
        return result

    async def async_set(self, attr: str, value: str) -> None:
        if self.stream is not None:
            # stream.async_set waits for the device to confirm via push
            await self.stream.async_set(attr, value)
            return
        # polling: send, then re-poll once per second for up to 5s until applied,
        # so the entity reflects the confirmed value immediately rather than at
        # the next scheduled poll.
        assert self.client is not None
        await self.client.async_set(attr, value)
        loop = asyncio.get_running_loop()
        end = loop.time() + 5
        data = await self.client.async_get_state()
        while str(data.get(attr)) != str(value) and loop.time() < end:
            await asyncio.sleep(1)
            data = await self.client.async_get_state()
        self.async_set_updated_data(data)
