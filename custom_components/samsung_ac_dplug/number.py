"""Number platform for Samsung AC (DPLUG/2878): sleep/on/off timers, energy target."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_OFFTIMER, ATTR_ONTIMER, ATTR_SETKWH, ATTR_SLEEP
from .coordinator import SamsungAcCoordinator
from .entity import SamsungAcEntity


@dataclass(frozen=True, kw_only=True)
class AcNumber(NumberEntityDescription):
    attr: str


NUMBERS: tuple[AcNumber, ...] = (
    AcNumber(
        key="sleep_timer",
        translation_key="sleep_timer",
        attr=ATTR_SLEEP,
        native_min_value=0,
        native_max_value=1440,
        native_step=30,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        icon="mdi:power-sleep",
        entity_category=EntityCategory.CONFIG,
    ),
    AcNumber(
        key="on_timer",
        translation_key="on_timer",
        attr=ATTR_ONTIMER,
        native_min_value=0,
        native_max_value=1440,
        native_step=30,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        icon="mdi:timer",
        entity_category=EntityCategory.CONFIG,
    ),
    AcNumber(
        key="off_timer",
        translation_key="off_timer",
        attr=ATTR_OFFTIMER,
        native_min_value=0,
        native_max_value=1440,
        native_step=30,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        icon="mdi:timer-off",
        entity_category=EntityCategory.CONFIG,
    ),
    AcNumber(
        key="energy_target",
        translation_key="energy_target",
        attr=ATTR_SETKWH,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        native_unit_of_measurement="kWh",
        mode=NumberMode.BOX,
        icon="mdi:lightning-bolt",
        entity_category=EntityCategory.CONFIG,
    ),
)


PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    state = coordinator.data or {}
    async_add_entities(
        SamsungAcNumber(coordinator, desc) for desc in NUMBERS if desc.attr in state
    )


class SamsungAcNumber(SamsungAcEntity, NumberEntity):
    entity_description: AcNumber

    def __init__(self, coordinator: SamsungAcCoordinator, description: AcNumber) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._duid}_{description.key}"

    @property
    def native_value(self) -> float | None:
        v = self._state.get(self.entity_description.attr)
        return float(int(v)) if v and v.lstrip("-").isdigit() else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set(self.entity_description.attr, str(int(value)))
