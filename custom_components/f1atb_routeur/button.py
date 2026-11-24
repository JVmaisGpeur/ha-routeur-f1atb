"""Bouton de calibration de la puissance du ballon."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([F1atbCalibrate(entry.runtime_data)])


class F1atbCalibrate(F1atbEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "calibrate")

    @property
    def available(self) -> bool:
        return super().available and not self.coordinator.calibrating and not self.coordinator.read_only

    async def async_press(self) -> None:
        await self.coordinator.async_calibrate()
