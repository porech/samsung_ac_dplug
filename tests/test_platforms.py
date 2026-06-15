"""Switch/select/number/sensor, diagnostics and remaining climate/command paths."""
from datetime import datetime

from homeassistant.const import ATTR_ENTITY_ID
from samsung_dplug import PowerUsageEntry

from custom_components.samsung_ac_dplug.const import DOMAIN
from custom_components.samsung_ac_dplug.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .common import setup_live, setup_polling


def _suffixed(hass, domain, suffix):
    return next(e for e in hass.states.async_entity_ids(domain) if e.endswith(suffix))


def _only(hass, domain):
    ids = hass.states.async_entity_ids(domain)
    assert ids, f"no {domain} entity"
    return ids[0]


async def test_switch_turn_off(hass):
    # Live mode: coordinator.async_set goes straight to the stream (no re-poll loop).
    _, stream = await setup_live(hass)
    ent = _suffixed(hass, "switch", "auto_clean")
    assert hass.states.get(ent).state == "on"
    await hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: ent}, blocking=True)
    stream.async_set.assert_any_await("AC_ADD_AUTOCLEAN", "Off")


async def test_switch_turn_on(hass):
    _, stream = await setup_live(hass)
    ent = _suffixed(hass, "switch", "sterilize")  # Off in STATE
    assert hass.states.get(ent).state == "off"
    await hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: ent}, blocking=True)
    stream.async_set.assert_any_await("AC_ADD_STERILIZE", "On")


async def test_filter_life_unknown_when_counter_untracked(hass):
    from .common import STATE

    # used > total -> not a trustworthy figure -> None -> "unknown".
    await setup_polling(hass, {**STATE, "AC_ADD2_FILTER_USE_TIME": "600", "AC_ADD2_FILTERTIME": "500"})
    assert hass.states.get(_suffixed(hass, "sensor", "filter_life")).state == "unknown"


async def test_number_set_value(hass):
    _, stream = await setup_live(hass)
    ent = _suffixed(hass, "number", "sleep_timer")
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: ent, "value": 60}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_SLEEP", "60")


async def test_select_option(hass):
    _, stream = await setup_live(hass)
    ent = _suffixed(hass, "select", "occupancy")
    assert hass.states.get(ent).state == "single"
    await hass.services.async_call(
        "select", "select_option", {ATTR_ENTITY_ID: ent, "option": "couple"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_OPERATION", "Couple")


async def test_sensor_values(hass):
    await setup_polling(hass)
    outdoor = _suffixed(hass, "sensor", "outdoor_temperature")
    assert hass.states.get(outdoor).state == "25.0"  # 77 °F
    filter_life = _suffixed(hass, "sensor", "filter_life")
    assert hass.states.get(filter_life).state == "80"  # 1 - 100/500
    assert hass.states.get(_suffixed(hass, "sensor", "error_code")).state == "OK"


async def test_climate_controls(hass):
    _, stream = await setup_live(hass)
    cid = _only(hass, "climate")
    await hass.services.async_call("climate", "turn_off", {ATTR_ENTITY_ID: cid}, blocking=True)
    stream.async_set.assert_any_await("AC_FUN_POWER", "Off")
    await hass.services.async_call(
        "climate", "set_fan_mode", {ATTR_ENTITY_ID: cid, "fan_mode": "high"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_WINDLEVEL", "High")
    await hass.services.async_call(
        "climate", "set_swing_mode", {ATTR_ENTITY_ID: cid, "swing_mode": "vertical"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_DIRECTION", "SwingUD")
    await hass.services.async_call(
        "climate", "set_hvac_mode", {ATTR_ENTITY_ID: cid, "hvac_mode": "heat"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_OPMODE", "Heat")


async def test_diagnostics(hass):
    entry, _ = await setup_polling(hass)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert isinstance(diag, dict)


async def test_power_and_region_services(hass):
    _, client = await setup_polling(hass)
    cid = _only(hass, "climate")
    client.async_get_power_usage.return_value = [
        PowerUsageEntry(datetime(2026, 6, 17, 8, 0), 1.5, 1.0)
    ]
    resp = await hass.services.async_call(
        DOMAIN,
        "get_power_usage",
        {ATTR_ENTITY_ID: cid, "start": "2026-06-17 00:00:00", "unit": "hour"},
        blocking=True,
        return_response=True,
    )
    assert resp[cid]["usage"][0]["power_kwh"] == 1.5

    await hass.services.async_call(
        DOMAIN, "set_power_logging", {ATTR_ENTITY_ID: cid, "enable": True}, blocking=True
    )
    client.async_set_power_logging.assert_awaited_once_with(True)
    await hass.services.async_call(
        DOMAIN, "reset_power_logging", {ATTR_ENTITY_ID: cid}, blocking=True
    )
    client.async_reset_power_logging.assert_awaited_once()

    resp = await hass.services.async_call(
        DOMAIN, "get_region_code", {ATTR_ENTITY_ID: cid}, blocking=True, return_response=True
    )
    assert resp[cid]["code"] == "EU"
    await hass.services.async_call(
        DOMAIN, "set_region_code", {ATTR_ENTITY_ID: cid, "code": "US"}, blocking=True
    )
    client.async_set_region_code.assert_awaited_once_with("US")
    await hass.services.async_call(
        DOMAIN, "delete_schedule", {ATTR_ENTITY_ID: cid, "schedule_id": "0"}, blocking=True
    )
    client.async_delete_schedule.assert_awaited_once_with("0")
