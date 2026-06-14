"""Climate platform for Samsung AC (DPLUG/2878)."""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COMODE,
    ATTR_DIRECTION,
    ATTR_OPMODE,
    ATTR_POWER,
    ATTR_TEMPNOW,
    ATTR_TEMPSET,
    ATTR_WINDLEVEL,
    DEVICE_TO_FAN,
    DEVICE_TO_HVAC,
    DEVICE_TO_SWING,
    DOMAIN,
    FAN_TO_DEVICE,
    HVAC_TO_DEVICE,
    MAX_TEMP,
    MIN_TEMP,
    PRESETS,
    SWING_TO_DEVICE,
)
from .entity import SamsungAcEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SamsungAcClimate(hass.data[DOMAIN][entry.entry_id])])


class SamsungAcClimate(SamsungAcEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO]
    _attr_fan_modes = list(FAN_TO_DEVICE)
    _attr_swing_modes = list(SWING_TO_DEVICE)
    _attr_preset_modes = PRESETS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = self._duid

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._state.get(ATTR_POWER) == "Off":
            return HVACMode.OFF
        return DEVICE_TO_HVAC.get(self._state.get(ATTR_OPMODE), None)

    @property
    def current_temperature(self) -> float | None:
        v = self._state.get(ATTR_TEMPNOW)
        return float(v) if v and v.lstrip("-").isdigit() else None

    @property
    def target_temperature(self) -> float | None:
        v = self._state.get(ATTR_TEMPSET)
        return float(v) if v and v.isdigit() else None

    @property
    def fan_mode(self) -> str | None:
        return DEVICE_TO_FAN.get(self._state.get(ATTR_WINDLEVEL))

    @property
    def swing_mode(self) -> str | None:
        return DEVICE_TO_SWING.get(self._state.get(ATTR_DIRECTION))

    @property
    def preset_mode(self) -> str | None:
        return self._state.get(ATTR_COMODE)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set(ATTR_POWER, "Off")
            return
        if self._state.get(ATTR_POWER) == "Off":
            await self.coordinator.async_set(ATTR_POWER, "On")
        await self.coordinator.async_set(ATTR_OPMODE, HVAC_TO_DEVICE[hvac_mode])

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set(ATTR_POWER, "On")

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set(ATTR_POWER, "Off")

    async def async_set_temperature(self, **kwargs) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set(ATTR_TEMPSET, str(int(temp)))

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.async_set(ATTR_WINDLEVEL, FAN_TO_DEVICE[fan_mode])

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        await self.coordinator.async_set(ATTR_DIRECTION, SWING_TO_DEVICE[swing_mode])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set(ATTR_COMODE, preset_mode)
