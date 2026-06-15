"""Switch platform for Samsung AC (DPLUG/2878): purify (SPi) and auto-clean."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from samsung_dplug import OptionCode

from .const import (
    ATTR_AUTOCLEAN,
    ATTR_LIGHT,
    ATTR_SMARTON,
    ATTR_SPI,
    ATTR_STERILIZE,
    ATTR_WEATHER,
)
from .entity import SamsungAcEntity


@dataclass(frozen=True, kw_only=True)
class AcSwitch(SwitchEntityDescription):
    attr: str
    cap: Callable[[OptionCode], bool] | None = None


SWITCHES: tuple[AcSwitch, ...] = (
    AcSwitch(key="purify", translation_key="purify", attr=ATTR_SPI, icon="mdi:air-purifier", cap=lambda o: o.spi),
    AcSwitch(key="auto_clean", translation_key="auto_clean", attr=ATTR_AUTOCLEAN, icon="mdi:auto-fix"),
    AcSwitch(key="light", translation_key="light", attr=ATTR_LIGHT, icon="mdi:lightbulb"),
    AcSwitch(key="sterilize", translation_key="sterilize", attr=ATTR_STERILIZE, icon="mdi:water-percent"),
    AcSwitch(key="smart_on", translation_key="smart_on", attr=ATTR_SMARTON, icon="mdi:motion-sensor"),
    AcSwitch(key="weather", translation_key="weather", attr=ATTR_WEATHER, icon="mdi:weather-partly-cloudy"),
)


PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
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
