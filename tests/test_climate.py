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


async def test_set_temperature_sends_command(hass):
    _, client = await setup_polling(hass)
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
        assert "Samsung AC command failed" in str(err)
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
