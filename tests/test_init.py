"""Setup / unload / coordinator tests."""
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState

from .common import _arm_api, _entry, setup_live, setup_polling


async def _setup_live_stream(hass, *, connected=True, auth_failed=False):
    entry = _entry(live=True)
    entry.add_to_hass(hass)
    with patch("custom_components.samsung_ac_dplug.build_ssl_context", return_value=object()), patch(
        "custom_components.samsung_ac_dplug.SamsungAcStream"
    ) as mock_stream:
        s = _arm_api(mock_stream.return_value)
        s.state = {}
        s.connected = connected
        s.auth_failed = auth_failed
        s.start = AsyncMock()
        s.stop = AsyncMock()
        s.set_on_update = MagicMock()
        s.set_on_availability = MagicMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_live_auth_failed_is_setup_error(hass):
    entry = await _setup_live_stream(hass, auth_failed=True)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_live_not_connected_retries(hass):
    entry = await _setup_live_stream(hass, connected=False)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_and_unload_polling(hass):
    entry, client = await setup_polling(hass)
    assert entry.state is ConfigEntryState.LOADED
    client.async_get_state.assert_awaited()

    # A climate entity was created and reflects the polled state.
    climate_ids = hass.states.async_entity_ids("climate")
    assert len(climate_ids) == 1
    assert hass.states.get(climate_ids[0]).state == "cool"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_live_starts_stream(hass):
    entry, stream = await setup_live(hass)
    assert entry.state is ConfigEntryState.LOADED
    stream.start.assert_awaited_once()
    stream.set_on_update.assert_called_once()
    assert hass.states.async_entity_ids("climate")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    stream.stop.assert_awaited_once()


async def test_entities_unavailable_when_stream_disconnects(hass):
    entry, stream = await setup_live(hass)
    climate_id = hass.states.async_entity_ids("climate")[0]
    assert hass.states.get(climate_id).state != "unavailable"

    stream.connected = False
    entry.runtime_data.handle_availability(False)
    await hass.async_block_till_done()
    assert hass.states.get(climate_id).state == "unavailable"


async def test_expected_entities_created(hass):
    await setup_polling(hass)
    # humidity sensor (state has AC_ADD_HUMIDI) and the schedules sensor exist.
    sensors = hass.states.async_entity_ids("sensor")
    assert any(s.endswith("_humidity") for s in sensors)
    assert any("schedule" in s for s in sensors)
