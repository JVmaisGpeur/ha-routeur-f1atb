"""Capteurs du routeur F1ATB."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_TEMP_CHANNEL, CONF_TEMP_SOURCE
from .coordinator import F1atbCoordinator
from .entity import F1atbEntity


@dataclass(frozen=True, kw_only=True)
class F1atbSensorDescription(SensorEntityDescription):
    value: Callable[[F1atbCoordinator, dict], Any]
    attrs: Callable[[F1atbCoordinator, dict], dict] | None = None


def _state(c: F1atbCoordinator, key: str) -> float:
    return round(float(c.state.get(key) or 0), 3)


SENSORS: tuple[F1atbSensorDescription, ...] = (
    F1atbSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["solar", "waiting_surplus", "on_slot", "boost", "forced", "off", "blocked", "hot", "idle", "safety"],
        value=lambda c, d: d.get("status"),
        attrs=lambda c, d: d.get("status_info") or {},
    ),
    F1atbSensorDescription(
        key="routed_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value=lambda c, d: d.get("routed_power_w"),
        attrs=lambda c, d: {"measured": d.get("routed_measured"), "ballon_power_w": c.ballon_power_w},
    ),
    F1atbSensorDescription(
        key="routed_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c, d: _state(c, "energy_today_kwh"),
    ),
    F1atbSensorDescription(
        key="routed_energy_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c, d: _state(c, "energy_total_kwh"),
    ),
    F1atbSensorDescription(
        key="grid_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c, d: _state(c, "grid_today_kwh"),
    ),
    F1atbSensorDescription(
        key="opening",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda c, d: d.get("opening"),
        attrs=lambda c, d: {"action": d.get("action_title"), "is_triac": d.get("is_triac"), "on_off": d.get("on_off")},
    ),
    F1atbSensorDescription(
        key="force_remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value=lambda c, d: d.get("force_min"),
    ),
    F1atbSensorDescription(
        key="planning",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "on", "route"],
        value=lambda c, d: (d.get("slot") or {}).get("kind"),
        attrs=lambda c, d: {
            "slots": d.get("slots"),
            "current": d.get("slot"),
            "action": d.get("action_title"),
            "force_opening": d.get("force_opening"),
        },
    ),
    F1atbSensorDescription(
        key="external_control",
        value=lambda c, d: (d.get("external") or {}).get("controller") or "none",
        attrs=lambda c, d: _external_attrs(d.get("external")),
    ),
    F1atbSensorDescription(
        key="tariff",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c, d: d.get("tariff"),
    ),
    F1atbSensorDescription(
        key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda c, d: d.get("firmware"),
        attrs=lambda c, d: {"api": d.get("firmware_api"), "read_only": c.read_only, "read_only_reason": c.read_only_reason},
    ),
    F1atbSensorDescription(
        key="rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        value=lambda c, d: (d.get("system") or {}).get("rssi"),
    ),
    F1atbSensorDescription(
        key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_registry_enabled_default=False,
        value=lambda c, d: (d.get("system") or {}).get("uptime_h"),
    ),
)


def _external_attrs(ext: dict | None) -> dict:
    if not ext:
        return {"controller": None, "controlled_keys": [], "expires_at": None, "mode": None, "reason": None}
    expires = datetime.fromtimestamp(float(ext.get("expires_ts", 0)), tz=dt_util.UTC)
    return {
        "controller": ext.get("controller"),
        "controlled_keys": ext.get("keys", []),
        "expires_at": expires.isoformat(),
        "mode": ext.get("mode"),
        "reason": ext.get("reason"),
        "target_temperature": ext.get("target_temperature"),
    }


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: F1atbCoordinator = entry.runtime_data
    entities: list[SensorEntity] = [F1atbSensor(coordinator, d) for d in SENSORS]
    if entry.data.get(CONF_TEMP_SOURCE, "none") != "none":
        entities.append(F1atbWaterTemperature(coordinator))
    # Autres sondes du routeur (hors sonde du ballon)
    ballon_ch = int(entry.data.get(CONF_TEMP_CHANNEL, -1)) if entry.data.get(CONF_TEMP_SOURCE) == "router" else -1
    temps = (coordinator.data or {}).get("temperatures") or []
    for ch in range(4):
        if ch == ballon_ch:
            continue
        if ch < len(temps) and temps[ch] is not None:
            entities.append(F1atbProbe(coordinator, ch))
    async_add_entities(entities)


class F1atbSensor(F1atbEntity, SensorEntity):
    entity_description: F1atbSensorDescription

    def __init__(self, coordinator: F1atbCoordinator, description: F1atbSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator, self.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        fn = self.entity_description.attrs
        return fn(self.coordinator, self.data) if fn else None


class F1atbWaterTemperature(F1atbEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: F1atbCoordinator) -> None:
        super().__init__(coordinator, "water_temperature")

    @property
    def native_value(self) -> float | None:
        return self.data.get("water_temperature")


class F1atbProbe(F1atbEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: F1atbCoordinator, channel: int) -> None:
        super().__init__(coordinator, "probe_temperature")
        self._channel = channel
        self._attr_unique_id = f"{self._attr_unique_id}_{channel}"
        names = (coordinator.data or {}).get("temp_names") or []
        name = names[channel] if channel < len(names) and names[channel] else None
        self._attr_translation_placeholders = {"name": name or str(channel + 1)}

    @property
    def native_value(self) -> float | None:
        temps = self.data.get("temperatures") or []
        return temps[self._channel] if self._channel < len(temps) else None
