"""Config flow for Samsung AC (DPLUG/2878): guided onboarding + DHCP discovery."""
from __future__ import annotations

import asyncio

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from samsung_dplug import (
    AuthError,
    SamsungAcClient,
    SamsungAcError,
    async_probe,
    build_ssl_context,
)

from .const import (
    CONF_DUID,
    CONF_HOST,
    CONF_LIVE_UPDATES,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_LIVE_UPDATES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    duid_to_mac,
)


class SamsungAcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung AC DPLUG."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "SamsungAcOptionsFlow":
        return SamsungAcOptionsFlow()

    def __init__(self) -> None:
        self._host: str | None = None
        self._token: str | None = None
        self._duid: str | None = None
        self._token_discovered: bool = False
        self._ssl = None

    async def _ssl_ctx(self):
        if self._ssl is None:
            self._ssl = await self.hass.async_add_executor_job(build_ssl_context)
        return self._ssl

    # ---- entry points -------------------------------------------------
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["onboard", "manual"])

    async def async_step_onboard(self, user_input=None) -> ConfigFlowResult:
        """Informational only: how to get the unit onto the home Wi-Fi.

        We don't chain into IP entry here — once the unit joins Wi-Fi it is
        normally offered automatically via discovery; the user can also re-enter
        the flow and pick the manual option. So this step just ends.
        """
        if user_input is not None:
            return self.async_abort(reason="onboard_finished")
        # URLs are passed as placeholders: translation strings may not contain URLs.
        return self.async_show_form(
            step_id="onboard",
            data_schema=vol.Schema({}),
            last_step=True,
            description_placeholders={
                "python_url": "https://www.python.org/downloads/",
                "script_url": "https://github.com/porech/samsung_ac_dplug/releases/latest/download/provision.py",
            },
        )

    async def async_step_manual(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            return await self.async_step_token()
        schema = vol.Schema({vol.Required(CONF_HOST, default=self._host or ""): str})
        return self.async_show_form(step_id="manual", data_schema=schema)

    async def async_step_token(self, user_input=None) -> ConfigFlowResult:
        """Acquire a token via power-on, or accept one the user already has."""
        errors: dict[str, str] = {}
        if user_input is not None:
            manual = (user_input.get(CONF_TOKEN) or "").strip()
            try:
                if manual:
                    self._token = manual
                    self._token_discovered = False
                else:
                    client = SamsungAcClient(self._host, ssl_context=await self._ssl_ctx())
                    self._token = await client.async_get_token(power_on_timeout=40)
                    self._token_discovered = True
                self._duid = await self._discover()
            except AuthError:
                errors["base"] = "auth"
            except (SamsungAcError, asyncio.TimeoutError):
                errors["base"] = "no_token"
            else:
                # Offer to save a freshly discovered token before finishing, so the
                # user can reuse it next time instead of repeating the power-on dance.
                if self._token_discovered:
                    return await self.async_step_save_token()
                return await self._create()
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({vol.Optional(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={"host": self._host or ""},
            last_step=True,
        )

    async def async_step_save_token(self, user_input=None) -> ConfigFlowResult:
        """Show the freshly discovered token so the user can save it for next time."""
        if user_input is not None:
            return await self._create()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="save_token",
            data_schema=vol.Schema({}),
            description_placeholders={"host": self._host or "", "token": self._token or ""},
            last_step=True,
        )

    # ---- reauth -------------------------------------------------------
    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        self._host = entry_data[CONF_HOST]
        self._duid = entry_data.get(CONF_DUID)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            manual = (user_input.get(CONF_TOKEN) or "").strip()
            try:
                if manual:
                    self._token = manual
                else:
                    client = SamsungAcClient(self._host, ssl_context=await self._ssl_ctx())
                    self._token = await client.async_get_token(power_on_timeout=40)
                await self._discover()  # validates the new token
            except AuthError:
                errors["base"] = "auth"
            except (SamsungAcError, asyncio.TimeoutError):
                errors["base"] = "no_token"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates={CONF_TOKEN: self._token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={"host": self._host or ""},
        )

    # ---- reconfigure --------------------------------------------------
    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        """Let the user point an existing unit at a new IP address."""
        entry = self._get_reconfigure_entry()
        self._token = entry.data[CONF_TOKEN]
        self._duid = entry.data.get(CONF_DUID)
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            try:
                duid = await self._discover()  # validates host + token
            except AuthError:
                errors["base"] = "auth"
            except (SamsungAcError, asyncio.TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(duid)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: self._host}
                )
        schema = vol.Schema(
            {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )

    # ---- discovery ----------------------------------------------------
    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        self._host = discovery_info.ip
        duid = discovery_info.macaddress.replace(":", "").replace("-", "").upper()
        await self.async_set_unique_id(duid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        # Confirm it really is a DPLUG air-conditioner before bothering the user.
        if not await async_probe(self._host, await self._ssl_ctx()):
            return self.async_abort(reason="not_samsung_ac")
        self._duid = duid
        self.context["title_placeholders"] = {"name": f"Samsung AC {duid_to_mac(duid).upper()}"}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_token()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"host": self._host or ""},
        )

    # ---- helpers ------------------------------------------------------
    async def _discover(self) -> str:
        client = SamsungAcClient(self._host, token=self._token, ssl_context=await self._ssl_ctx())
        return await client.async_discover_duid()

    async def _create(self) -> ConfigFlowResult:
        await self.async_set_unique_id(self._duid)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
        return self.async_create_entry(
            # Title is the device's stable identity, not its (mutable) IP. The
            # DUID *is* the module's MAC, so show it as one. The host lives in
            # data[] and is kept fresh by the DHCP discovery step.
            title=f"Samsung AC {duid_to_mac(self._duid).upper()}",
            data={CONF_HOST: self._host, CONF_TOKEN: self._token, CONF_DUID: self._duid},
        )


class SamsungAcOptionsFlow(OptionsFlow):
    """Options: enable live (push) updates and set the refresh interval."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LIVE_UPDATES,
                    default=opts.get(CONF_LIVE_UPDATES, DEFAULT_LIVE_UPDATES),
                ): bool,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=5, max=3600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
