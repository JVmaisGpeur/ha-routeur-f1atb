"""Sélecteur du mode de fonctionnement."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALL_MODES, DOMAIN, MODE_EXTERNAL
from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([F1atbModeSelect(entry.runtime_data)])


class F1atbModeSelect(F1atbEntity, SelectEntity):
    _attr_options = ALL_MODES

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "operating_mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.effective_mode

    @property
    def extra_state_attributes(self) -> dict:
        c = self.coordinator
        ext = c.external
        return {
            "user_mode": c.user_mode,
            "prev_mode": c.state.get("prev_mode"),
            "controller": ext.get("controller") if ext else None,
            "external_mode": ext.get("mode") if ext else None,
            "manual_until": c.state.get("manual_until"),
            "reason": self.data.get("reason"),
            "read_only": c.read_only,
        }

    async def async_select_option(self, option: str) -> None:
        if option == MODE_EXTERNAL:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="external_not_selectable")
        await self.coordinator.async_set_mode(option)
