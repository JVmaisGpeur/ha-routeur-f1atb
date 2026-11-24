"""Services de l'intégration Routeur F1ATB."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN, EXTERNAL_KEYS, USER_MODES

ATTR_DEVICE_ID = "device_id"
ATTR_CONTROLLER = "controller"
ATTR_OVERRIDE = "override"

_BASE = {
    vol.Required(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_CONTROLLER): cv.string,
    vol.Optional(ATTR_OVERRIDE, default=False): cv.boolean,
}

SCHEMA_EXTERNAL = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required("active"): cv.boolean,
        vol.Required(ATTR_CONTROLLER): cv.string,
        vol.Optional("controlled_keys"): vol.All(cv.ensure_list, [vol.In(EXTERNAL_KEYS)]),
    }
)
SCHEMA_MODE = vol.Schema(
    {**_BASE, vol.Required("mode"): vol.In(USER_MODES), vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))}
)
SCHEMA_BOOST = vol.Schema(
    {
        **_BASE,
        vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
        vol.Optional("energy"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=20)),
        vol.Optional("until_temperature"): vol.All(vol.Coerce(float), vol.Range(min=20, max=80)),
    }
)
SCHEMA_TARGET = vol.Schema({**_BASE, vol.Required("temperature"): vol.All(vol.Coerce(float), vol.Range(min=30, max=75))})
SCHEMA_SIMPLE = vol.Schema(_BASE)
SCHEMA_CALIBRATE = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _coordinator(hass: HomeAssistant, device_id: str):
    device = dr.async_get(hass).async_get(device_id)
    if device:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry and entry.domain == DOMAIN and getattr(entry, "runtime_data", None):
                return entry.runtime_data
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="unknown_device")


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    async def set_external_control(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_set_external_control(
            call.data["active"], call.data[ATTR_CONTROLLER], call.data.get("controlled_keys")
        )

    async def set_mode(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_set_mode(
            call.data["mode"],
            duration_min=call.data.get("duration"),
            controller=call.data.get(ATTR_CONTROLLER),
            override=call.data[ATTR_OVERRIDE],
        )

    async def boost(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_boost(
            duration_min=call.data.get("duration"),
            energy_kwh=call.data.get("energy"),
            until_temperature=call.data.get("until_temperature"),
            controller=call.data.get(ATTR_CONTROLLER),
            override=call.data[ATTR_OVERRIDE],
        )

    async def cancel_boost(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_cancel_boost(controller=call.data.get(ATTR_CONTROLLER), override=call.data[ATTR_OVERRIDE])

    async def set_target_temperature(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_set_target(
            call.data["temperature"], controller=call.data.get(ATTR_CONTROLLER), override=call.data[ATTR_OVERRIDE]
        )

    async def calibrate(call: ServiceCall) -> None:
        coord = _coordinator(hass, call.data[ATTR_DEVICE_ID])
        await coord.async_calibrate()

    for name, handler, schema in (
        ("set_external_control", set_external_control, SCHEMA_EXTERNAL),
        ("set_mode", set_mode, SCHEMA_MODE),
        ("boost", boost, SCHEMA_BOOST),
        ("cancel_boost", cancel_boost, SCHEMA_SIMPLE),
        ("set_target_temperature", set_target_temperature, SCHEMA_TARGET),
        ("calibrate", calibrate, SCHEMA_CALIBRATE),
    ):
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
