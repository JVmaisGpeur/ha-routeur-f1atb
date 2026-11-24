"""Capteurs binaires du routeur F1ATB."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    c: F1atbCoordinator = entry.runtime_data
    async_add_entities(
        [
            F1atbConnected(c),
            F1atbFlag(c, "target_reached", lambda d, co: bool(d.get("reached")), {"method": lambda co: co.hot_method}),
            F1atbFlag(c, "boost_active", lambda d, co: bool(d.get("boost_active")), None),
            F1atbFlag(c, "thermostat_open", lambda d, co: bool(d.get("thermostat_open")), None),
        ]
    )


class F1atbConnected(F1atbEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.last_update_success)


class F1atbFlag(F1atbEntity, BinarySensorEntity):
    def __init__(self, coordinator: F1atbCoordinator, key: str, fn, attrs) -> None:
        super().__init__(coordinator, key)
        self._fn = fn
        self._attrs = attrs

    @property
    def is_on(self) -> bool:
        return self._fn(self.data, self.coordinator)

    @property
    def extra_state_attributes(self) -> dict | None:
        if not self._attrs:
            return None
        return {k: f(self.coordinator) for k, f in self._attrs.items()}
