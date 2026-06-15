"""Tests for the Samsung AC (DPLUG) config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from samsung_dplug import AuthError, SamsungAcError

from custom_components.samsung_ac_dplug.const import DOMAIN

DUID = "F8042E3F89A6"
HOST = "192.168.1.53"
TITLE = "Samsung AC F8:04:2E:3F:89:A6"

_INIT = "custom_components.samsung_ac_dplug"
_FLOW = "custom_components.samsung_ac_dplug.config_flow"


@pytest.fixture(autouse=True)
def _no_entry_setup():
    """Don't actually set up (connect) the entry a successful flow creates."""
    with patch(f"{_INIT}.async_setup_entry", return_value=True):
        yield


def _patches():
    """Patch the blocking SSL build and the protocol client used by the flow."""
    return (
        patch(f"{_FLOW}.build_ssl_context", return_value=object()),
        patch(f"{_FLOW}.SamsungAcClient"),
    )


async def _to_token_step(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})
    assert result["step_id"] == "token"
    return result


async def test_manual_flow_acquires_token_then_offers_to_save(hass):
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        inst = mock_client.return_value
        inst.async_get_token = AsyncMock(return_value="tok-123")
        inst.async_discover_duid = AsyncMock(return_value=DUID)

        result = await _to_token_step(hass)
        # Empty token field -> acquire via power-on -> save-token step.
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["step_id"] == "save_token"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {"host": HOST, "token": "tok-123", "duid": DUID}
    inst.async_get_token.assert_awaited_once()


async def test_manual_flow_with_known_token_skips_save(hass):
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        inst = mock_client.return_value
        inst.async_get_token = AsyncMock(return_value="should-not-be-called")
        inst.async_discover_duid = AsyncMock(return_value=DUID)

        result = await _to_token_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "my-token"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["token"] == "my-token"
    inst.async_get_token.assert_not_called()


async def test_token_auth_error_shows_form_error(hass):
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        inst = mock_client.return_value
        inst.async_get_token = AsyncMock(side_effect=AuthError("bad token"))

        result = await _to_token_step(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {"base": "auth"}


async def test_token_no_token_error(hass):
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        inst = mock_client.return_value
        inst.async_get_token = AsyncMock(side_effect=SamsungAcError("timeout"))

        result = await _to_token_step(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["errors"] == {"base": "no_token"}


async def test_onboard_step_just_ends(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "onboard"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "onboard"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "onboard_finished"


async def test_duplicate_unit_aborts(hass):
    MockConfigEntry(domain=DOMAIN, unique_id=DUID, data={"host": HOST}).add_to_hass(hass)
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        inst = mock_client.return_value
        inst.async_discover_duid = AsyncMock(return_value=DUID)
        result = await _to_token_step(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "my-token"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_updates_host(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DUID, data={"host": "192.168.1.99", "token": "tok", "duid": DUID}
    )
    entry.add_to_hass(hass)
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        mock_client.return_value.async_discover_duid = AsyncMock(return_value=DUID)
        result = await entry.start_reconfigure_flow(hass)
        assert result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": HOST})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == HOST


async def test_reconfigure_rejects_wrong_device(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DUID, data={"host": HOST, "token": "tok", "duid": DUID}
    )
    entry.add_to_hass(hass)
    p_ssl, p_client = _patches()
    with p_ssl, p_client as mock_client:
        mock_client.return_value.async_discover_duid = AsyncMock(return_value="AABBCCDDEEFF")
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.77"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_options_flow(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DUID, data={"host": HOST}, options={})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"live_updates": False, "scan_interval": 45}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"live_updates": False, "scan_interval": 45}
