"""Consigne de température et puissance du ballon."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import parsers as P
from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    c: F1atbCoordinator = entry.runtime_data
    entities = [F1atbTarget(c), F1atbPower(c)]
    if c.config and c.config.firmware.api == P.FW_JSON:
        entities.append(F1atbForceOpening(c))
    async_add_entities(entities)


class F1atbTarget(F1atbEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 30
    _attr_native_max_value = 75
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "target_temperature")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.target_temp

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_target(value)


class F1atbPower(F1atbEntity, NumberEntity):
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 100
    _attr_native_max_value = 10000
    _attr_native_step = 10
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "water_heater_power")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self.coordinator.ballon_power_w

    @property
    def extra_state_attributes(self) -> dict:
        return {"source": self.coordinator.power_source, "origin": self.coordinator.state.get("power_origin")}

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_power(value, "declared")


class F1atbForceOpening(F1atbEntity, NumberEntity):
    """« Ouverture si forcée » (17.xx) : écrite dans le routeur seulement quand l'utilisateur la change."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 5
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "force_opening")

    @property
    def native_value(self) -> int | None:
        act = self.coordinator.action_config
        return act.force_opening if act else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_force_opening(value)
