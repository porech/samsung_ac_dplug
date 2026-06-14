"""Switch platform for Samsung AC (DPLUG/2878): purify (SPi) and auto-clean."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_AUTOCLEAN, ATTR_SPI, DOMAIN
from .entity import SamsungAcEntity


@dataclass(frozen=True, kw_only=True)
class AcSwitch(SwitchEntityDescription):
    attr: str


SWITCHES: tuple[AcSwitch, ...] = (
    AcSwitch(key="purify", translation_key="purify", attr=ATTR_SPI, icon="mdi:air-purifier"),
    AcSwitch(key="auto_clean", translation_key="auto_clean", attr=ATTR_AUTOCLEAN, icon="mdi:auto-fix"),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    state = coordinator.data or {}
    async_add_entities(
        SamsungAcSwitch(coordinator, desc) for desc in SWITCHES if desc.attr in state
    )


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
