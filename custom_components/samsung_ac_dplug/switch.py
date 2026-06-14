"""Switch platform for Samsung AC (DPLUG/2878): purify (SPi) and auto-clean."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from samsung_dplug import OptionCode

from .const import ATTR_AUTOCLEAN, ATTR_SPI, DOMAIN
from .entity import SamsungAcEntity


@dataclass(frozen=True, kw_only=True)
class AcSwitch(SwitchEntityDescription):
    attr: str
    cap: Callable[[OptionCode], bool] | None = None


SWITCHES: tuple[AcSwitch, ...] = (
    AcSwitch(key="purify", translation_key="purify", attr=ATTR_SPI, icon="mdi:air-purifier", cap=lambda o: o.spi),
    AcSwitch(key="auto_clean", translation_key="auto_clean", attr=ATTR_AUTOCLEAN, icon="mdi:auto-fix"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    state = coordinator.data or {}
    opts = OptionCode.from_state(state)

    def supported(desc: AcSwitch) -> bool:
        if desc.attr not in state:
            return False
        if desc.cap is not None:
            return opts is not None and desc.cap(opts)
        return True

    async_add_entities(SamsungAcSwitch(coordinator, desc) for desc in SWITCHES if supported(desc))


class SamsungAcSwitch(SamsungAcEntity, SwitchEntity):
    entity_description: AcSwitch

    def __init__(self, coordinator, description: AcSwitch):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._duid}_{description.key}"

    @property
    def is_on(self) -> bool:
        return self._state.get(self.entity_description.attr) == "On"

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set(self.entity_description.attr, "On")

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set(self.entity_description.attr, "Off")
