"""Service schemas/helpers for the extra device commands.

Power usage/logging, nickname and region code are protocol features offered by
the official app, exposed here as services.
"""
from __future__ import annotations

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CODE,
    ATTR_ENABLE,
    ATTR_END,
    ATTR_NICKNAME,
    ATTR_START,
    ATTR_UNIT,
)

GET_POWER_USAGE_SCHEMA = {
    vol.Required(ATTR_START): cv.datetime,
    vol.Optional(ATTR_END): cv.datetime,
    vol.Required(ATTR_UNIT, default="hour"): vol.In(["hour", "day"]),
}

SET_POWER_LOGGING_SCHEMA = {vol.Required(ATTR_ENABLE): cv.boolean}

SET_NICKNAME_SCHEMA = {vol.Required(ATTR_NICKNAME): cv.string}

SET_REGION_CODE_SCHEMA = {vol.Required(ATTR_CODE): cv.string}

# HA option -> library Unit value.
UNIT_TO_LIB = {"hour": "Hour", "day": "Day"}


def power_usage_to_dict(entry) -> dict:
    return {
        "time": entry.time.isoformat(),
        "power_kwh": round(entry.power_kwh, 3),
        "hours": round(entry.hours, 2),
    }
