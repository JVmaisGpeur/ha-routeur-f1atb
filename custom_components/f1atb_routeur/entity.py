"""Base des entités : un appareil Home Assistant par routeur."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import F1atbCoordinator


class F1atbEntity(CoordinatorEntity[F1atbCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: F1atbCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{uid}_{key}"
        self._attr_translation_key = key
        cfg = coordinator.config
        info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=(cfg.name if cfg else None) or entry.title,
            manufacturer=MANUFACTURER,
            model="Routeur multi-sources (RMS, ESP32)",
            configuration_url=coordinator.client.base_url,
        )
        if cfg and cfg.firmware.version and cfg.firmware.version != "?":
            info["sw_version"] = cfg.firmware.version
        mac = (coordinator.system or {}).get("mac")
        if mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
        self._attr_device_info = info

    @property
    def data(self) -> dict:
        return self.coordinator.data or {}
