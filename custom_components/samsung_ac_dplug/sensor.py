"""Sensor platform for Samsung AC (DPLUG/2878): extra data not in the climate entity."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_ERROR,
    ATTR_FILTER_MAX,
    ATTR_FILTER_TIME,
    ATTR_HUMIDITY,
    ATTR_OUTDOOR_TEMP,
    ATTR_TEMPNOW,
    ATTR_USED_TIME,
)
import datetime

from .coordinator import SamsungAcCoordinator
from .entity import SamsungAcEntity
from .schedule_helpers import schedule_to_dict


def _to_int(v: str | None) -> int | None:
    return int(v) if v and v.lstrip("-").isdigit() else None


def _outdoor_c(v: str | None) -> float | None:
    """AC_OUTDOOR_TEMP is reported in Fahrenheit -> convert to Celsius."""
    i = _to_int(v)
    return round((i - 32) * 5 / 9, 1) if i is not None else None


def _error(v: str | None) -> str:
    if not v or v in ("NULL", "0"):
        return "OK"
    return v


def _filter_life(state: dict[str, str]) -> int | None:
    """Remaining filter life as a percentage.

    used = hours since last clean (AC_ADD2_FILTER_USE_TIME),
    total = cleaning interval / total hours (AC_ADD2_FILTERTIME).
    """
    used = _to_int(state.get(ATTR_FILTER_TIME))
    total = _to_int(state.get(ATTR_FILTER_MAX))
    # Some units report sentinel values (e.g. used=10000, total=500) when the
    # filter counter is not actually tracked; only report a trustworthy figure.
    if used is None or total is None or total <= 0 or used > total:
        return None
    return round((1 - used / total) * 100)


@dataclass(frozen=True, kw_only=True)
class AcSensor(SensorEntityDescription):
    attr: str
    convert: Callable[[str | None], Any] = _to_int
    # When set, the value is computed from the full coordinator state instead of
    # a single attribute (used for derived sensors like filter life %).
    value_from_state: Callable[[dict[str, str]], Any] | None = None
    # Extra attributes that must also be present in state for the sensor to be
    # created (in addition to `attr`).
    requires: tuple[str, ...] = ()


SENSORS: tuple[AcSensor, ...] = (
    AcSensor(
        key="temperature",
        translation_key="temperature",
        attr=ATTR_TEMPNOW,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AcSensor(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        attr=ATTR_OUTDOOR_TEMP,
        convert=_outdoor_c,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AcSensor(
        key="humidity",
        translation_key="humidity",
        attr=ATTR_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        convert=_to_int,
    ),
    AcSensor(
        key="used_time",
        translation_key="used_time",
        attr=ATTR_USED_TIME,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AcSensor(
        key="filter_use_time",
        translation_key="filter_use_time",
        attr=ATTR_FILTER_TIME,
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AcSensor(
        key="filter_life",
        translation_key="filter_life",
        attr=ATTR_FILTER_TIME,
        requires=(ATTR_FILTER_MAX,),
        value_from_state=_filter_life,
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AcSensor(
        key="error",
        translation_key="error",
        attr=ATTR_ERROR,
        convert=_error,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    state = coordinator.data or {}

    def supported(desc: AcSensor) -> bool:
        return desc.attr in state and all(req in state for req in desc.requires)

    entities: list[SensorEntity] = [
        SamsungAcSensor(coordinator, desc) for desc in SENSORS if supported(desc)
    ]
    entities.append(SamsungAcClockSensor(coordinator))
    entities.append(SamsungAcSchedulesSensor(coordinator))
    async_add_entities(entities)


class SamsungAcClockSensor(SamsungAcEntity, SensorEntity):
    """The unit's internal UTC clock (diagnostic), read from the AuthToken response."""

    _attr_translation_key = "device_clock"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SamsungAcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._duid}_device_clock"

    @property
    def native_value(self) -> datetime.datetime | None:
        return self.coordinator.device_clock


class SamsungAcSchedulesSensor(SamsungAcEntity, SensorEntity):
    """Diagnostic view of the unit's built-in scheduler.

    State is the number of on-device schedules; the schedules themselves (in
    local time) are exposed as an attribute. The list is refreshed once when the
    entity is added and again after any schedule service call; use the
    ``get_schedules`` service to refresh on demand.
    """

    _attr_translation_key = "schedules"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SamsungAcCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._duid}_schedules"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Pull the schedule list once on startup, without blocking setup.
        self.hass.async_create_task(self._async_initial_refresh())

    async def _async_initial_refresh(self) -> None:
        try:
            await self.coordinator.async_refresh_schedules()
        except Exception:  # noqa: BLE001 - diagnostic only; don't break setup
            self.coordinator.logger.debug("initial schedule refresh failed", exc_info=True)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.schedules)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"schedules": [schedule_to_dict(s) for s in self.coordinator.schedules]}


class SamsungAcSensor(SamsungAcEntity, SensorEntity):
    entity_description: AcSensor

    def __init__(self, coordinator: SamsungAcCoordinator, description: AcSensor) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._duid}_{description.key}"

    @property
    def native_value(self) -> Any:
        if self.entity_description.value_from_state is not None:
            return self.entity_description.value_from_state(self._state)
        return self.entity_description.convert(self._state.get(self.entity_description.attr))
