"""Sensor platform for Samsung AC (DPLUG/2878): extra data not in the climate entity."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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
    ATTR_FILTER_TIME,
    ATTR_OUTDOOR_TEMP,
    ATTR_TEMPNOW,
    ATTR_USED_TIME,
)
from .entity import SamsungAcEntity


def _to_int(v):
    return int(v) if v and v.lstrip("-").isdigit() else None


def _outdoor_c(v):
    """AC_OUTDOOR_TEMP is reported in Fahrenheit -> convert to Celsius."""
    i = _to_int(v)
    return round((i - 32) * 5 / 9, 1) if i is not None else None


def _error(v):
    if v in (None, "", "NULL", "0"):
        return "OK"
    return v


@dataclass(frozen=True, kw_only=True)
class AcSensor(SensorEntityDescription):
    attr: str
    convert: Callable = _to_int


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
    async_add_entities(
        SamsungAcSensor(coordinator, desc) for desc in SENSORS if desc.attr in state
    )


class SamsungAcSensor(SamsungAcEntity, SensorEntity):
    entity_description: AcSensor

    def __init__(self, coordinator, description: AcSensor):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._duid}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.convert(self._state.get(self.entity_description.attr))
