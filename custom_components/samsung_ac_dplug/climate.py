"""Climate platform for Samsung AC (DPLUG/2878)."""
from __future__ import annotations

import functools

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from samsung_dplug import SamsungAcError


def _service(func):
    """Surface device/communication failures in a service action as a clean
    HomeAssistantError (ServiceValidationError from input checks passes through)."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except SamsungAcError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    return wrapper

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
    DEVICE_TO_PRESET,
    DEVICE_TO_SWING,
    FAN_TO_DEVICE,
    HVAC_TO_DEVICE,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_TO_DEVICE,
    SERVICE_DELETE_SCHEDULE,
    SERVICE_GET_SCHEDULES,
    SERVICE_SET_SCHEDULE,
    SWING_ALL_TO_DEVICE,
)
from .const import (
    ATTR_CODE,
    ATTR_ENABLE,
    ATTR_END,
    ATTR_NICKNAME,
    ATTR_SCHEDULE_ID,
    ATTR_START,
    ATTR_UNIT,
    DOMAIN,
    SERVICE_GET_POWER_USAGE,
    SERVICE_GET_REGION_CODE,
    SERVICE_RESET_POWER_LOGGING,
    SERVICE_SET_NICKNAME,
    SERVICE_SET_POWER_LOGGING,
    SERVICE_SET_REGION_CODE,
)
from .command_helpers import (
    GET_POWER_USAGE_SCHEMA,
    SET_NICKNAME_SCHEMA,
    SET_POWER_LOGGING_SCHEMA,
    SET_REGION_CODE_SCHEMA,
    UNIT_TO_LIB,
    power_usage_to_dict,
)
from .entity import SamsungAcEntity
from .schedule_helpers import (
    DELETE_SCHEDULE_SCHEMA,
    SET_SCHEDULE_SCHEMA,
    schedule_from_call,
    schedule_to_dict,
)


PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SamsungAcClimate(entry.runtime_data)])

    # On-device scheduler, exposed as services on the climate entity.
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_GET_SCHEDULES,
        None,
        "async_get_schedules_service",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE, SET_SCHEDULE_SCHEMA, "async_set_schedule_service"
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_SCHEDULE, DELETE_SCHEDULE_SCHEMA, "async_delete_schedule_service"
    )

    # Extra device commands: power usage/logging, nickname, region code.
    platform.async_register_entity_service(
        SERVICE_GET_POWER_USAGE,
        GET_POWER_USAGE_SCHEMA,
        "async_get_power_usage_service",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_POWER_LOGGING, SET_POWER_LOGGING_SCHEMA, "async_set_power_logging_service"
    )
    platform.async_register_entity_service(
        SERVICE_RESET_POWER_LOGGING, None, "async_reset_power_logging_service"
    )
    platform.async_register_entity_service(
        SERVICE_SET_NICKNAME, SET_NICKNAME_SCHEMA, "async_set_nickname_service"
    )
    platform.async_register_entity_service(
        SERVICE_GET_REGION_CODE,
        None,
        "async_get_region_code_service",
        supports_response=SupportsResponse.ONLY,
    )
    platform.async_register_entity_service(
        SERVICE_SET_REGION_CODE, SET_REGION_CODE_SCHEMA, "async_set_region_code_service"
    )


class SamsungAcClimate(SamsungAcEntity, ClimateEntity):
    _attr_name = None
    _attr_translation_key = "samsung_ac"
    _attr_target_temperature_step = 1
    _attr_fan_modes = list(FAN_TO_DEVICE)
    # We declare TURN_ON/TURN_OFF explicitly, so opt out of the legacy
    # compatibility path (and its deprecation warning).
    _enable_turn_on_off_backwards_compatibility = False

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
        # Some units report a fixed directional vane position outside the base
        # set; surface it only while it is actually in use so the selector stays
        # uncluttered on units that don't use these positions.
        current = DEVICE_TO_SWING.get(self._state.get(ATTR_DIRECTION))
        if current is not None and current not in modes:
            modes.append(current)
        return modes

    @property
    def preset_modes(self) -> list[str]:
        # Only presets the OptionCode proves are supported.
        opts = self._options
        if not opts:
            return ["none"]
        presets = ["none"]
        if opts.quiet:
            presets.append("quiet")
        if opts.turbo_softcool:
            presets += ["fast_turbo", "comfort"]
        if opts.dlight_cool:
            presets.append("dlight_cool")
        if opts.ecorun_cool or opts.ecorun_heat:
            presets.append("smart_saver")
        if opts.color_of_wind:
            presets += ["color_of_wind_alps", "color_of_wind_florida", "color_of_wind_savanna"]
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
        return DEVICE_TO_PRESET.get(self._state.get(ATTR_COMODE))

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
        await self.coordinator.async_set(ATTR_DIRECTION, SWING_ALL_TO_DEVICE[swing_mode])

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set(ATTR_COMODE, PRESET_TO_DEVICE[preset_mode])

    # -- on-device scheduler services ---------------------------------------
    @_service
    async def async_get_schedules_service(self, **kwargs) -> ServiceResponse:
        """Return the schedules stored on the unit (built-in scheduler)."""
        schedules = await self.coordinator.async_refresh_schedules()
        return {"schedules": [schedule_to_dict(s) for s in schedules]}

    @_service
    async def async_set_schedule_service(self, **kwargs) -> None:
        """Create or edit an on-device on/off schedule."""
        await self.coordinator.async_set_schedule(schedule_from_call(kwargs))

    @_service
    async def async_delete_schedule_service(self, **kwargs) -> None:
        """Delete an on-device schedule by id."""
        await self.coordinator.async_delete_schedule(kwargs[ATTR_SCHEDULE_ID])

    # -- extra device commands ----------------------------------------------
    @_service
    async def async_get_power_usage_service(self, **kwargs) -> ServiceResponse:
        """Return the unit's recorded power-usage history."""
        end = kwargs.get(ATTR_END) or dt_util.now()
        entries = await self.coordinator.async_get_power_usage(
            kwargs[ATTR_START], end, UNIT_TO_LIB[kwargs[ATTR_UNIT]]
        )
        return {"usage": [power_usage_to_dict(e) for e in entries]}

    @_service
    async def async_set_power_logging_service(self, **kwargs) -> None:
        await self.coordinator.async_set_power_logging(kwargs[ATTR_ENABLE])

    @_service
    async def async_reset_power_logging_service(self, **kwargs) -> None:
        await self.coordinator.async_reset_power_logging()

    @_service
    async def async_set_nickname_service(self, **kwargs) -> None:
        await self.coordinator.async_set_nickname(kwargs[ATTR_NICKNAME])

    @_service
    async def async_get_region_code_service(self, **kwargs) -> ServiceResponse:
        return {"code": await self.coordinator.async_get_region_code()}

    @_service
    async def async_set_region_code_service(self, **kwargs) -> None:
        await self.coordinator.async_set_region_code(kwargs[ATTR_CODE])
