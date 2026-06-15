"""Climate entity and schedule/command service tests."""
from homeassistant.const import ATTR_ENTITY_ID
from samsung_dplug import Schedule

from custom_components.samsung_ac_dplug.const import DOMAIN

from .common import setup_polling


async def _climate_id(hass):
    return hass.states.async_entity_ids("climate")[0]


async def test_climate_state_and_attributes(hass):
    await setup_polling(hass)
    state = hass.states.get(await _climate_id(hass))
    assert state.state == "cool"
    assert state.attributes["current_temperature"] == 25.0
    assert state.attributes["temperature"] == 23.0
    assert state.attributes["fan_mode"] == "auto"


async def test_climate_capabilities_and_power_off(hass):
    from .common import STATE

    # Power off, plus a capability code that enables quiet/turbo/dlight/eco/color and
    # left-right louver — exercises the preset/swing/hvac branches.
    code = 32 | 8 | 8192 | 16 | 128 | 1024
    state = {**STATE, "AC_FUN_POWER": "Off", "AC_ADD2_OPTIONCODE": str(code)}
    await setup_polling(hass, state)
    st = hass.states.get(await _climate_id(hass))
    assert st.state == "off"
    assert "quiet" in st.attributes["preset_modes"]
    assert "both" in st.attributes["swing_modes"]
    assert "heat" in st.attributes["hvac_modes"]


async def test_climate_fahrenheit_unit(hass):
    from .common import STATE

    await setup_polling(hass, {**STATE, "AC_ADD2_OPTIONCODE": "4"})  # FAHRENHEIT bit
    st = hass.states.get(await _climate_id(hass))
    # The entity reports 60 °F as its min; HA converts to the system unit (°C),
    # so a value well below the 16 °C metric minimum proves the Fahrenheit path.
    assert st.attributes["min_temp"] == 15.6


async def test_climate_without_capability_code(hass):
    from .common import STATE

    state = {k: v for k, v in STATE.items() if k != "AC_ADD2_OPTIONCODE"}
    await setup_polling(hass, state)
    st = hass.states.get(await _climate_id(hass))
    assert st.attributes["preset_modes"] == ["none"]


async def test_climate_fixed_vane_swing(hass):
    from .common import STATE

    await setup_polling(hass, {**STATE, "AC_FUN_DIRECTION": "Indirect"})
    st = hass.states.get(await _climate_id(hass))
    assert "indirect" in st.attributes["swing_modes"]


async def test_set_preset_and_hvac_from_off(hass):
    from homeassistant.const import ATTR_ENTITY_ID

    from .common import STATE, setup_live

    _, stream = await setup_live(hass, {**STATE, "AC_FUN_POWER": "Off"})
    cid = await _climate_id(hass)
    await hass.services.async_call(
        "climate", "set_preset_mode", {ATTR_ENTITY_ID: cid, "preset_mode": "none"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_COMODE", "Off")
    # From OFF, setting a mode powers the unit on first, then sets the mode.
    await hass.services.async_call(
        "climate", "set_hvac_mode", {ATTR_ENTITY_ID: cid, "hvac_mode": "cool"}, blocking=True
    )
    stream.async_set.assert_any_await("AC_FUN_POWER", "On")
    stream.async_set.assert_any_await("AC_FUN_OPMODE", "Cool")


async def test_set_temperature_sends_command(hass):
    # Polling path: async_set re-reads state until it reflects the change.
    from .common import STATE

    _, client = await setup_polling(hass)
    client.async_get_state.return_value = {**STATE, "AC_FUN_TEMPSET": "21"}
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: await _climate_id(hass), "temperature": 21},
        blocking=True,
    )
    client.async_set.assert_any_await("AC_FUN_TEMPSET", "21")


async def test_set_schedule_service(hass):
    _, client = await setup_polling(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {
            ATTR_ENTITY_ID: await _climate_id(hass),
            "time": "07:00:00",
            "power": "on",
            "repeat": "daily",
        },
        blocking=True,
    )
    client.async_set_schedule.assert_awaited_once()
    sched = client.async_set_schedule.await_args.args[0]
    assert isinstance(sched, Schedule)
    assert (sched.hour, sched.minute) == (7, 0)
    assert sched.attrs == {"AC_FUN_POWER": "On"}


async def test_get_schedules_service_returns_response(hass):
    _, client = await setup_polling(hass)
    client.async_get_schedules.return_value = [
        Schedule(schedule_id="0", hour=8, minute=30, repeat="EveryDay", attrs={"AC_FUN_POWER": "Off"})
    ]
    resp = await hass.services.async_call(
        DOMAIN,
        "get_schedules",
        {ATTR_ENTITY_ID: await _climate_id(hass)},
        blocking=True,
        return_response=True,
    )
    entity_id = await _climate_id(hass)
    schedules = resp[entity_id]["schedules"]
    assert schedules[0]["time"] == "08:30"
    assert schedules[0]["power"] == "off"


async def test_set_nickname_service(hass):
    _, client = await setup_polling(hass)
    await hass.services.async_call(
        DOMAIN,
        "set_nickname",
        {ATTR_ENTITY_ID: await _climate_id(hass), "nickname": "Studio"},
        blocking=True,
    )
    client.async_set_nickname.assert_awaited_once_with("Studio")


async def test_service_wraps_device_error(hass):
    from homeassistant.exceptions import HomeAssistantError
    from samsung_dplug import SamsungAcError

    _, client = await setup_polling(hass)
    client.async_set_nickname.side_effect = SamsungAcError("device said no")
    raised = False
    try:
        await hass.services.async_call(
            DOMAIN,
            "set_nickname",
            {ATTR_ENTITY_ID: await _climate_id(hass), "nickname": "X"},
            blocking=True,
        )
    except HomeAssistantError as err:
        raised = True
        assert err.translation_key == "command_failed"
    assert raised


async def test_set_schedule_weekly_requires_days(hass):
    from homeassistant.exceptions import HomeAssistantError

    _, client = await setup_polling(hass)
    raised = False
    try:
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                ATTR_ENTITY_ID: await _climate_id(hass),
                "time": "07:00:00",
                "power": "on",
                "repeat": "weekly",
            },
            blocking=True,
        )
    except HomeAssistantError:
        raised = True
    assert raised
    client.async_set_schedule.assert_not_called()
