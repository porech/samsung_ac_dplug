"""Helpers to translate between HA service calls and library Schedules.

These services drive the air conditioner's **built-in** scheduler: it runs off
the module's own clock and fires even while Home Assistant is offline, and it
only switches the unit on or off. For anything richer (temperature, mode, fan,
multi-step scenarios) use Home Assistant automations instead.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from samsung_dplug import (
    EVERYDAY_TYPE,
    EVERYWEEK,
    ONCE,
    Schedule,
    weekdays_to_mask,
)

from .const import (
    ATTR_SCHEDULE_DAYS,
    ATTR_SCHEDULE_ENABLED,
    ATTR_SCHEDULE_ID,
    ATTR_SCHEDULE_POWER,
    ATTR_SCHEDULE_REPEAT,
    ATTR_SCHEDULE_TIME,
    DOMAIN,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKLY,
)

# Lowercase 3-letter weekday names -> Python weekday() (Mon=0 .. Sun=6).
_WEEKDAY_TO_PY = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_WEEKDAYS = vol.All(cv.ensure_list, [vol.In(list(_WEEKDAY_TO_PY))])

_REPEAT_TO_LIB = {REPEAT_ONCE: ONCE, REPEAT_DAILY: EVERYDAY_TYPE, REPEAT_WEEKLY: EVERYWEEK}
_LIB_TO_REPEAT = {v: k for k, v in _REPEAT_TO_LIB.items()}

# `repeat` is Required (with a default) so the HA UI shows the frequency radio
# group as always-active rather than gated behind an opt-in checkbox.
SET_SCHEDULE_SCHEMA: dict[Any, Any] = {
    vol.Required(ATTR_SCHEDULE_TIME): cv.time,
    vol.Required(ATTR_SCHEDULE_POWER): vol.In(["on", "off"]),
    vol.Required(ATTR_SCHEDULE_REPEAT, default=REPEAT_ONCE): vol.In(
        [REPEAT_ONCE, REPEAT_DAILY, REPEAT_WEEKLY]
    ),
    vol.Optional(ATTR_SCHEDULE_DAYS): _WEEKDAYS,
    vol.Optional(ATTR_SCHEDULE_ENABLED, default=True): cv.boolean,
    vol.Optional(ATTR_SCHEDULE_ID): cv.string,
}

DELETE_SCHEDULE_SCHEMA: dict[Any, Any] = {vol.Required(ATTR_SCHEDULE_ID): cv.string}


def schedule_from_call(data: dict[str, Any]) -> Schedule:
    """Build a library Schedule from validated set_schedule service data.

    Raises ServiceValidationError when 'once'/'weekly' is requested without any
    day, since those repeat types need at least one day on the wire.
    """
    repeat = _REPEAT_TO_LIB[data[ATTR_SCHEDULE_REPEAT]]
    days = data.get(ATTR_SCHEDULE_DAYS) or []
    if repeat in (ONCE, EVERYWEEK) and not days:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="schedule_needs_day"
        )
    when = data[ATTR_SCHEDULE_TIME]
    power = "On" if data[ATTR_SCHEDULE_POWER] == "on" else "Off"
    return Schedule(
        schedule_id=data.get(ATTR_SCHEDULE_ID, ""),
        hour=when.hour,
        minute=when.minute,
        repeat=repeat,
        days=weekdays_to_mask(_WEEKDAY_TO_PY[d] for d in days),
        enabled=data[ATTR_SCHEDULE_ENABLED],
        attrs={"AC_FUN_POWER": power},
    )


def schedule_to_dict(sched: Schedule) -> dict[str, Any]:
    """Render a Schedule as a plain dict for service responses / attributes."""
    power = sched.power
    return {
        ATTR_SCHEDULE_ID: sched.schedule_id,
        ATTR_SCHEDULE_TIME: f"{sched.hour:02d}:{sched.minute:02d}",
        ATTR_SCHEDULE_POWER: power.lower() if power else None,
        ATTR_SCHEDULE_REPEAT: _LIB_TO_REPEAT.get(sched.repeat, sched.repeat),
        ATTR_SCHEDULE_DAYS: sched.day_names,
        ATTR_SCHEDULE_ENABLED: sched.enabled,
    }
