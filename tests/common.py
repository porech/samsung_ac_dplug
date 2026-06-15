"""Shared helpers for the integration tests."""
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.samsung_ac_dplug.const import DOMAIN

DUID = "F8042E3F89A6"
HOST = "192.168.1.53"
_INIT = "custom_components.samsung_ac_dplug"

# A representative DeviceState snapshot (device-side values).
STATE = {
    "AC_FUN_POWER": "On",
    "AC_FUN_OPMODE": "Cool",
    "AC_FUN_TEMPSET": "23",
    "AC_FUN_TEMPNOW": "25",
    "AC_FUN_WINDLEVEL": "Auto",
    "AC_FUN_COMODE": "Off",
    "AC_FUN_DIRECTION": "SwingUD",
    "AC_ADD2_OPTIONCODE": "2",  # SPI capability
    "AC_ADD_HUMIDI": "50",
}


def _entry(live: bool) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DUID,
        title="Samsung AC F8:04:2E:3F:89:A6",
        data={"host": HOST, "token": "tok", "duid": DUID},
        options={"live_updates": live, "scan_interval": 30},
    )


def _arm_api(mock):
    """Give a mocked client/stream the async methods the integration calls."""
    mock.start_from = None
    mock.async_set = AsyncMock()
    mock.async_set_schedule = AsyncMock()
    mock.async_delete_schedule = AsyncMock()
    mock.async_get_schedules = AsyncMock(return_value=[])
    mock.async_get_power_usage = AsyncMock(return_value=[])
    mock.async_set_power_logging = AsyncMock()
    mock.async_reset_power_logging = AsyncMock()
    mock.async_set_nickname = AsyncMock()
    mock.async_get_region_code = AsyncMock(return_value="EU")
    mock.async_set_region_code = AsyncMock()
    return mock


async def setup_polling(hass, state=None):
    """Set up the integration in polling mode; return (entry, client_mock)."""
    entry = _entry(live=False)
    entry.add_to_hass(hass)
    with patch(f"{_INIT}.build_ssl_context", return_value=object()), patch(
        f"{_INIT}.SamsungAcClient"
    ) as mock_client:
        inst = _arm_api(mock_client.return_value)
        inst.async_get_state = AsyncMock(return_value=state or STATE)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, inst


async def setup_live(hass, state=None):
    """Set up the integration in live (push) mode; return (entry, stream_mock)."""
    entry = _entry(live=True)
    entry.add_to_hass(hass)
    with patch(f"{_INIT}.build_ssl_context", return_value=object()), patch(
        f"{_INIT}.SamsungAcStream"
    ) as mock_stream:
        inst = _arm_api(mock_stream.return_value)
        inst.state = state or STATE
        inst.connected = True
        inst.auth_failed = False
        inst.duid = DUID
        inst.start = AsyncMock()
        inst.stop = AsyncMock()
        inst.set_on_update = MagicMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, inst
