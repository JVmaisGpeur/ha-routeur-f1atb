"""Interrupteur control_enabled : « Piloter le routeur » / « Affichage seulement »."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([F1atbControlEnabled(entry.runtime_data)])


class F1atbControlEnabled(F1atbEntity, SwitchEntity):
    """Entité stable lue par les pilotes externes (ex. Chef d'orchestre énergie).

    En marche : Home Assistant et les pilotes peuvent commander le routeur.
    À l'arrêt : l'intégration affiche tout mais n'envoie plus aucune commande.
    """

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "control_enabled")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.control_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_control_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_control_enabled(False)
