"""Select platform for Samsung AC (DPLUG/2878): occupancy, beep volume, front panel."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_OPERATION,
    ATTR_PANEL,
    ATTR_VOLUME,
    OPERATION_TO_DEVICE,
    PANEL_TO_DEVICE,
    VOLUME_TO_DEVICE,
)
from .entity import SamsungAcEntity


@dataclass(frozen=True, kw_only=True)
class AcSelect(SelectEntityDescription):
    attr: str
    value_map: dict[str, str]


SELECTS: tuple[AcSelect, ...] = (
    AcSelect(
        key="occupancy",
        translation_key="occupancy",
        attr=ATTR_OPERATION,
        value_map=OPERATION_TO_DEVICE,
    ),
    AcSelect(
        key="beep_volume",
        translation_key="beep_volume",
        attr=ATTR_VOLUME,
        value_map=VOLUME_TO_DEVICE,
    ),
    AcSelect(
        key="panel",
        translation_key="panel",
        attr=ATTR_PANEL,
        value_map=PANEL_TO_DEVICE,
    ),
)


PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    state = coordinator.data or {}
    async_add_entities(
        SamsungAcSelect(coordinator, desc) for desc in SELECTS if desc.attr in state
    )


class SamsungAcSelect(SamsungAcEntity, SelectEntity):
    entity_description: AcSelect

    def __init__(self, coordinator, description: AcSelect):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._duid}_{description.key}"
        self._attr_options = list(description.value_map)
        self._inverse = {v: k for k, v in description.value_map.items()}

    @property
    def current_option(self) -> str | None:
        return self._inverse.get(self._state.get(self.entity_description.attr))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set(
            self.entity_description.attr, self.entity_description.value_map[option]
        )
