"""Config flow for Samsung AC (DPLUG/2878): guided onboarding + DHCP discovery."""
from __future__ import annotations

import asyncio

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from samsung_dplug import (
    AuthError,
    SamsungAcClient,
    SamsungAcError,
    async_probe,
    build_ssl_context,
)

from .const import CONF_DUID, CONF_HOST, CONF_TOKEN, DOMAIN


class SamsungAcConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung AC DPLUG."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._token: str | None = None
        self._duid: str | None = None
        self._ssl = None

    async def _ssl_ctx(self):
        if self._ssl is None:
            self._ssl = await self.hass.async_add_executor_job(build_ssl_context)
        return self._ssl

    # ---- entry points -------------------------------------------------
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["onboard", "manual"])

    async def async_step_onboard(self, user_input=None) -> ConfigFlowResult:
        """Informational: how to get the unit onto the home Wi-Fi."""
        if user_input is not None:
            return await self.async_step_manual()
        return self.async_show_form(step_id="onboard", data_schema=vol.Schema({}), last_step=False)

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
                else:
                    client = SamsungAcClient(self._host, ssl_context=await self._ssl_ctx())
                    self._token = await client.async_get_token(power_on_timeout=40)
                self._duid = await self._discover()
            except AuthError:
                errors["base"] = "auth"
            except (SamsungAcError, asyncio.TimeoutError):
                errors["base"] = "no_token"
            else:
                return await self._create()
        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema({vol.Optional(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={"host": self._host or ""},
            last_step=True,
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
        self.context["title_placeholders"] = {"name": f"Samsung AC {self._host}"}
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
            title=f"Samsung AC {self._host}",
            data={CONF_HOST: self._host, CONF_TOKEN: self._token, CONF_DUID: self._duid},
        )
