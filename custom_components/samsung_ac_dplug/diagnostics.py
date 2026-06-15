"""Diagnostics for the Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from samsung_dplug import OptionCode

from .coordinator import SamsungAcConfigEntry

TO_REDACT = {"token", "duid", "host"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SamsungAcConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    state = coordinator.data or {}
    opts = OptionCode.from_state(state)
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "device_state": state,
        "capabilities": opts.as_dict() if opts else None,
        "live": coordinator.stream is not None,
    }
