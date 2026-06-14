"""Base entity for the Samsung AC (DPLUG/2878) integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from samsung_dplug import OptionCode

from .const import ATTR_COOL_CAP, DOMAIN, MANUFACTURER
from .coordinator import SamsungAcCoordinator


class SamsungAcEntity(CoordinatorEntity[SamsungAcCoordinator]):
    """Common base: shares one device per physical unit (keyed by DUID)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SamsungAcCoordinator) -> None:
        super().__init__(coordinator)
        self._duid = coordinator.entry.data["duid"]

    @property
    def _state(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _options(self) -> OptionCode | None:
        return OptionCode.from_state(self._state)

    @property
    def device_info(self) -> DeviceInfo:
        data = self._state
        model = "Samsung AC (DPLUG)"
        cool = data.get(ATTR_COOL_CAP)
        if cool and cool.isdigit():
            model = f"Samsung AC ~{int(cool) * 100} W cooling (DPLUG/2878)"
        return DeviceInfo(
            identifiers={(DOMAIN, self._duid)},
            name=self.coordinator.entry.title,
            manufacturer=MANUFACTURER,
            model=model,
            connections={("mac", _mac_from_duid(self._duid))},
        )


def _mac_from_duid(duid: str) -> str:
    """DUID is the MAC without separators -> format as aa:bb:cc:dd:ee:ff."""
    d = duid[:12].lower()
    return ":".join(d[i : i + 2] for i in range(0, 12, 2))
