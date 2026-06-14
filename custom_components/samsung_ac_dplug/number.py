"""Number platform for Samsung AC (DPLUG/2878): sleep timer."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SLEEP, DOMAIN
from .entity import SamsungAcEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if ATTR_SLEEP in (coordinator.data or {}):
        async_add_entities([SamsungAcSleep(coordinator)])


class SamsungAcSleep(SamsungAcEntity, NumberEntity):
    _attr_translation_key = "sleep_timer"
    _attr_native_min_value = 0
    _attr_native_max_value = 1440
    _attr_native_step = 30
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:power-sleep"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._duid}_sleep_timer"

    @property
    def native_value(self) -> float | None:
        v = self._state.get(ATTR_SLEEP)
        return float(v) if v and v.isdigit() else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set(ATTR_SLEEP, str(int(value)))
