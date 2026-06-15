"""Setup / unload / coordinator tests."""
from homeassistant.config_entries import ConfigEntryState

from .common import setup_live, setup_polling


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


async def test_expected_entities_created(hass):
    await setup_polling(hass)
    # humidity sensor (state has AC_ADD_HUMIDI) and the schedules sensor exist.
    sensors = hass.states.async_entity_ids("sensor")
    assert any(s.endswith("_humidity") for s in sensors)
    assert any("schedule" in s for s in sensors)
