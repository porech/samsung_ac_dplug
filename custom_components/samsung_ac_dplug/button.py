"""Button platform for Samsung AC (DPLUG/2878): reset the filter indicator."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CLEAR_FILTER
from .entity import SamsungAcEntity

# Value written to AC_ADD_CLEAR_FILTER_ALARM to reset the filter indicator.
#
# UNVERIFIED: the attribute AC_ADD_CLEAR_FILTER_ALARM does not appear in any
# control call in the decompiled official app (jungfrau); the FilterReplacement
# screen only re-writes the filter interval (AC_ADD2_FILTERTIME). The only
# evidence is FilterAlarmEnum {Clear, RequestClear, Set, Unknown}. Per the issue
# we default to "0" until the real reset value can be confirmed on a device.
RESET_FILTER_VALUE = "0"


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    state = coordinator.data or {}
    if ATTR_CLEAR_FILTER in state:
        async_add_entities([SamsungAcResetFilterButton(coordinator)])


class SamsungAcResetFilterButton(SamsungAcEntity, ButtonEntity):
    _attr_translation_key = "reset_filter"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._duid}_reset_filter"

    async def async_press(self) -> None:
        await self.coordinator.async_set(ATTR_CLEAR_FILTER, RESET_FILTER_VALUE)
