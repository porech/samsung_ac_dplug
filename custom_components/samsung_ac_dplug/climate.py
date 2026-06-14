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
    ATTR_WARM_CAP,
    ATTR_WINDLEVEL,
    DEVICE_TO_FAN,
    DEVICE_TO_HVAC,
    DEVICE_TO_SWING,
    DOMAIN,
    FAN_TO_DEVICE,
    HVAC_TO_DEVICE,
    MAX_TEMP,
    MIN_TEMP,
    SWING_TO_DEVICE,
)
from .entity import SamsungAcEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SamsungAcClimate(hass.data[DOMAIN][entry.entry_id])])


class SamsungAcClimate(SamsungAcEntity, ClimateEntity):
    _attr_name = None
    _attr_target_temperature_step = 1
    _attr_fan_modes = list(FAN_TO_DEVICE)

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = self._duid

    @property
    def temperature_unit(self) -> str:
        opts = self._options
        if opts and opts.fahrenheit:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def min_temp(self) -> float:
        return 60 if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else MIN_TEMP

    @property
    def max_temp(self) -> float:
        return 86 if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else MAX_TEMP

    @property
    def hvac_modes(self) -> list[HVACMode]:
        # Cooling-side modes are universal; heating only if the unit supports it.
        modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY]
        opts = self._options
        heater = opts.heater if opts else bool((self._state.get(ATTR_WARM_CAP) or "0").isdigit() and int(self._state.get(ATTR_WARM_CAP) or 0) > 0)
        if heater:
            modes += [HVACMode.HEAT, HVACMode.AUTO]
        return modes

    @property
    def swing_modes(self) -> list[str]:
        # "both" (Rotation) needs the horizontal louver, so it is only offered
        # together with horizontal when the unit has left/right swing.
        opts = self._options
        modes = ["off", "vertical"]
        if opts and opts.lr_swing:
            modes += ["horizontal", "both"]
        return modes

    @property
    def preset_modes(self) -> list[str]:
        # Only presets the OptionCode proves are supported.
        opts = self._options
        presets = ["Off"]
        if opts:
            if opts.quiet:
                presets.append("Quiet")
            if opts.turbo_softcool:
                presets += ["TurboMode", "SoftCool"]
        return presets

    @property
    def supported_features(self) -> ClimateEntityFeature:
        # Only advertise a control if the device actually reports its attribute.
        feats = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        state = self._state
        if ATTR_TEMPSET in state:
            feats |= ClimateEntityFeature.TARGET_TEMPERATURE
        if ATTR_WINDLEVEL in state:
            feats |= ClimateEntityFeature.FAN_MODE
        if ATTR_DIRECTION in state:
            feats |= ClimateEntityFeature.SWING_MODE
        if ATTR_COMODE in state:
            feats |= ClimateEntityFeature.PRESET_MODE
        return feats

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
