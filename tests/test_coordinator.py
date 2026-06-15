"""Coordinator behaviour: polling errors, live refresh, async_set re-poll, reconnect."""
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from samsung_dplug import AuthError, SamsungAcError

from .common import STATE, _arm_api, _entry, setup_live, setup_polling

_INIT = "custom_components.samsung_ac_dplug"


async def _setup_polling_state(hass, get_state):
    entry = _entry(live=False)
    entry.add_to_hass(hass)
    with patch(f"{_INIT}.build_ssl_context", return_value=object()), patch(
        f"{_INIT}.SamsungAcClient"
    ) as mock_client:
        inst = _arm_api(mock_client.return_value)
        inst.async_get_state = get_state
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_polling_auth_error_is_setup_error(hass):
    entry = await _setup_polling_state(hass, AsyncMock(side_effect=AuthError("bad")))
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_polling_device_error_retries(hass):
    entry = await _setup_polling_state(hass, AsyncMock(side_effect=SamsungAcError("down")))
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_live_refresh_returns_state(hass):
    entry, _ = await setup_live(hass)
    coord = entry.runtime_data
    await coord.async_refresh()  # exercises _async_update_data in push mode
    assert coord.data["AC_FUN_POWER"] == "On"


async def test_polling_async_set_repolls_until_applied(hass):
    entry, client = await setup_polling(hass)
    coord = entry.runtime_data
    client.async_set = AsyncMock()
    # First re-poll still shows the old value, second shows the new one.
    client.async_get_state = AsyncMock(
        side_effect=[{**STATE, "AC_FUN_POWER": "On"}, {**STATE, "AC_FUN_POWER": "Off"}]
    )
    with patch(f"{_INIT}.coordinator.asyncio.sleep", AsyncMock()):
        await coord.async_set("AC_FUN_POWER", "Off")
    assert coord.data["AC_FUN_POWER"] == "Off"


async def test_schedules_sensor_initial_refresh_failure_is_swallowed(hass):
    entry = _entry(live=False)
    entry.add_to_hass(hass)
    with patch(f"{_INIT}.build_ssl_context", return_value=object()), patch(
        f"{_INIT}.SamsungAcClient"
    ) as mock_client:
        inst = _arm_api(mock_client.return_value)
        inst.async_get_state = AsyncMock(return_value=STATE)
        inst.async_get_schedules = AsyncMock(side_effect=SamsungAcError("nope"))
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_reconnect_restores_availability(hass):
    entry, stream = await setup_live(hass)
    cid = hass.states.async_entity_ids("climate")[0]
    stream.connected = False
    entry.runtime_data.handle_availability(False)
    await hass.async_block_till_done()
    assert hass.states.get(cid).state == "unavailable"
    stream.connected = True
    entry.runtime_data.handle_availability(True)
    await hass.async_block_till_done()
    assert hass.states.get(cid).state != "unavailable"
