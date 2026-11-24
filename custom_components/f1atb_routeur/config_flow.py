"""Installation et options de l'intégration Routeur F1ATB."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector as sel
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from . import parsers as P
from .api import F1atbClient, F1atbError, RouterConfig
from .const import (
    CONF_ACTION,
    CONF_ALLOW_EXTERNAL,
    CONF_DEADLINE,
    CONF_DECLARED_POWER,
    CONF_FORCE_API,
    CONF_GRID_ENTITY,
    CONF_HC_END,
    CONF_HC_ENTITY,
    CONF_HC_START,
    CONF_HOST,
    CONF_HOT_ENERGY,
    CONF_HOT_METHOD,
    CONF_HYSTERESIS,
    CONF_MAX_MANUAL_MIN,
    CONF_METER_ENTITY,
    CONF_POWER_SOURCE,
    CONF_SAFETY_TEMP,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_TEMP,
    CONF_TEMP_CHANNEL,
    CONF_TEMP_ENTITY,
    CONF_TEMP_SOURCE,
    DEFAULT_DEADLINE,
    DEFAULT_DECLARED_POWER,
    DEFAULT_HC_END,
    DEFAULT_HC_START,
    DEFAULT_HOT_ENERGY,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_MANUAL_MIN,
    DEFAULT_SAFETY_TEMP,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    HOT_METHODS,
    POWER_SOURCES,
    TEMP_SOURCES,
)

BALLON_KEYS = (
    CONF_ACTION, CONF_TEMP_SOURCE, CONF_TEMP_CHANNEL, CONF_TEMP_ENTITY, CONF_POWER_SOURCE,
    CONF_DECLARED_POWER, CONF_METER_ENTITY, CONF_HOT_METHOD, CONF_HOT_ENERGY,
)


async def _probe(hass, host: str) -> tuple[RouterConfig, dict]:
    client = F1atbClient(async_get_clientsession(hass), host)
    await client.async_detect()
    cfg = await client.async_get_config()
    try:
        system = await client.async_get_system()
    except F1atbError:
        system = {}
    return cfg, system


def _unique_id(cfg: RouterConfig, system: dict, host: str) -> str:
    if system.get("mac"):
        return format_mac(system["mac"])
    return str(system.get("hostname") or cfg.name or host)


def _actions_label(cfg: RouterConfig) -> str:
    parts = []
    for a in cfg.actions:
        if a.mode == "inactive":
            continue
        kind = "triac" if a.is_triac else "relais"
        parts.append(f"{a.title} ({kind})")
    return ", ".join(parts) or "—"


def _select(options: list[str], key: str) -> sel.SelectSelector:
    return sel.SelectSelector(
        sel.SelectSelectorConfig(options=options, translation_key=key, mode=sel.SelectSelectorMode.DROPDOWN)
    )


def _ballon_schema(cfg: RouterConfig | None, current: dict) -> vol.Schema:
    actions = [a for a in (cfg.actions if cfg else []) if a.mode != "inactive"] or (cfg.actions if cfg else [])
    action_opts = [
        sel.SelectOptionDict(value=str(a.index), label=f"{a.index} – {a.title} ({'triac' if a.is_triac else 'relais'})")
        for a in actions
    ] or [sel.SelectOptionDict(value="0", label="0")]
    temp_names = cfg.temp_names if cfg else []
    chan_opts = [
        sel.SelectOptionDict(value=str(c), label=f"{c + 1} – {temp_names[c] if c < len(temp_names) and temp_names[c] else '—'}")
        for c in range(4)
    ]
    default_action = str(current.get(CONF_ACTION, action_opts[0]["value"]))
    return vol.Schema(
        {
            vol.Required(CONF_ACTION, default=default_action): sel.SelectSelector(
                sel.SelectSelectorConfig(options=action_opts, mode=sel.SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_TEMP_SOURCE, default=current.get(CONF_TEMP_SOURCE, "router" if any(temp_names) else "none")): _select(TEMP_SOURCES, CONF_TEMP_SOURCE),
            vol.Optional(CONF_TEMP_CHANNEL, default=str(current.get(CONF_TEMP_CHANNEL, 0))): sel.SelectSelector(
                sel.SelectSelectorConfig(options=chan_opts, mode=sel.SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(CONF_TEMP_ENTITY, description={"suggested_value": current.get(CONF_TEMP_ENTITY)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_POWER_SOURCE, default=current.get(CONF_POWER_SOURCE, "declared")): _select(POWER_SOURCES, CONF_POWER_SOURCE),
            vol.Optional(CONF_DECLARED_POWER, default=current.get(CONF_DECLARED_POWER, DEFAULT_DECLARED_POWER)): sel.NumberSelector(
                sel.NumberSelectorConfig(min=100, max=10000, step=10, unit_of_measurement="W", mode=sel.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_METER_ENTITY, description={"suggested_value": current.get(CONF_METER_ENTITY)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_HOT_METHOD, default=current.get(CONF_HOT_METHOD, "temperature" if any(temp_names) else "thermostat")): _select(HOT_METHODS, CONF_HOT_METHOD),
            vol.Optional(CONF_HOT_ENERGY, default=current.get(CONF_HOT_ENERGY, DEFAULT_HOT_ENERGY)): sel.NumberSelector(
                sel.NumberSelectorConfig(min=0.5, max=20, step=0.1, unit_of_measurement="kWh", mode=sel.NumberSelectorMode.BOX)
            ),
        }
    )


def _check_ballon(data: dict) -> dict[str, str]:
    errors: dict[str, str] = {}
    if data.get(CONF_TEMP_SOURCE) == "entity" and not data.get(CONF_TEMP_ENTITY):
        errors[CONF_TEMP_ENTITY] = "entity_required"
    if data.get(CONF_POWER_SOURCE) == "meter" and not data.get(CONF_METER_ENTITY):
        errors[CONF_METER_ENTITY] = "entity_required"
    if data.get(CONF_HOT_METHOD) == "temperature" and data.get(CONF_TEMP_SOURCE) == "none":
        errors[CONF_HOT_METHOD] = "temperature_needs_probe"
    return errors


def _clean_ballon(data: dict) -> dict:
    out = {k: data.get(k) for k in BALLON_KEYS if data.get(k) not in (None, "")}
    out[CONF_ACTION] = int(out.get(CONF_ACTION, 0))
    out[CONF_TEMP_CHANNEL] = int(out.get(CONF_TEMP_CHANNEL, 0))
    out[CONF_DECLARED_POWER] = float(out.get(CONF_DECLARED_POWER, DEFAULT_DECLARED_POWER))
    out[CONF_HOT_ENERGY] = float(out.get(CONF_HOT_ENERGY, DEFAULT_HOT_ENERGY))
    return out


def _autonomous_schema(current: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TARGET_TEMP, default=current.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)): sel.NumberSelector(
                sel.NumberSelectorConfig(min=30, max=75, step=0.5, unit_of_measurement="°C", mode=sel.NumberSelectorMode.BOX)
            ),
            vol.Optional(CONF_HC_ENTITY, description={"suggested_value": current.get(CONF_HC_ENTITY)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain=["binary_sensor", "input_boolean", "switch"])
            ),
            vol.Required(CONF_HC_START, default=current.get(CONF_HC_START, DEFAULT_HC_START)): sel.TimeSelector(),
            vol.Required(CONF_HC_END, default=current.get(CONF_HC_END, DEFAULT_HC_END)): sel.TimeSelector(),
            vol.Required(CONF_DEADLINE, default=current.get(CONF_DEADLINE, DEFAULT_DEADLINE)): sel.TimeSelector(),
        }
    )


class F1atbConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._cfg: RouterConfig | None = None
        self._system: dict = {}
        self._ballon: dict = {}

    # ------------------------------------------------ saisie de l'adresse
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                self._cfg, self._system = await _probe(self.hass, host)
            except F1atbError:
                errors["base"] = "cannot_connect"
            else:
                self._host = host
                await self.async_set_unique_id(_unique_id(self._cfg, self._system, host))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return await self.async_step_water_heater()
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required(CONF_HOST): str}), errors=errors
        )

    # ------------------------------------------------ découverte
    async def async_step_dhcp(self, discovery_info) -> ConfigFlowResult:
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        return await self._async_discovered(discovery_info.ip)

    async def async_step_integration_discovery(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        return await self._async_discovered(discovery_info[CONF_HOST])

    async def _async_discovered(self, host: str) -> ConfigFlowResult:
        self._async_abort_entries_match({CONF_HOST: host})
        try:
            self._cfg, self._system = await _probe(self.hass, host)
        except F1atbError:
            return self.async_abort(reason="cannot_connect")
        self._host = host
        await self.async_set_unique_id(_unique_id(self._cfg, self._system, host))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self.context["title_placeholders"] = {"name": self._cfg.name, "host": host}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """L'utilisateur confirme que c'est bien un routeur à ajouter."""
        assert self._cfg is not None
        if user_input is not None:
            return await self.async_step_water_heater()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._cfg.name,
                "host": str(self._host),
                "version": self._cfg.firmware.version,
                "actions": _actions_label(self._cfg),
            },
        )

    # ------------------------------------------------ ballon
    async def async_step_water_heater(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _check_ballon(user_input)
            if not errors:
                self._ballon = _clean_ballon(user_input)
                return await self.async_step_autonomous()
        assert self._cfg is not None
        return self.async_show_form(
            step_id="water_heater",
            data_schema=_ballon_schema(self._cfg, user_input or {}),
            errors=errors,
            description_placeholders={
                "name": self._cfg.name,
                "version": self._cfg.firmware.version,
                "untested": "" if self._cfg.firmware.tested else "⚠️",
            },
        )

    async def async_step_autonomous(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._cfg is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._cfg.name,
                data={CONF_HOST: self._host, **self._ballon},
                options={k: v for k, v in user_input.items() if v not in (None, "")},
            )
        has_on_slot = any(s.kind == "on" for a in self._cfg.actions if a.index == self._ballon.get(CONF_ACTION) for s in a.slots)
        return self.async_show_form(
            step_id="autonomous",
            data_schema=_autonomous_schema({}),
            description_placeholders={"on_slot": "✔" if has_on_slot else "—"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return F1atbOptionsFlow()


class F1atbOptionsFlow(OptionsFlow):
    """Options : pilotage, heures creuses, sécurité ; puis réglages du ballon."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        cur = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            self._opts = {k: v for k, v in user_input.items() if v not in (None, "")}
            return await self.async_step_water_heater()
        schema = _autonomous_schema(cur).extend(
            {
                vol.Required(CONF_HYSTERESIS, default=cur.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)): sel.NumberSelector(
                    sel.NumberSelectorConfig(min=0.5, max=10, step=0.5, unit_of_measurement="°C", mode=sel.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_SAFETY_TEMP, default=cur.get(CONF_SAFETY_TEMP, DEFAULT_SAFETY_TEMP)): sel.NumberSelector(
                    sel.NumberSelectorConfig(min=50, max=85, step=1, unit_of_measurement="°C", mode=sel.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_MAX_MANUAL_MIN, default=cur.get(CONF_MAX_MANUAL_MIN, DEFAULT_MAX_MANUAL_MIN)): sel.NumberSelector(
                    sel.NumberSelectorConfig(min=30, max=1440, step=30, unit_of_measurement="min", mode=sel.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_ALLOW_EXTERNAL, default=cur.get(CONF_ALLOW_EXTERNAL, True)): sel.BooleanSelector(),
                vol.Optional(CONF_GRID_ENTITY, description={"suggested_value": cur.get(CONF_GRID_ENTITY)}): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain="sensor", device_class="power")
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): sel.NumberSelector(
                    sel.NumberSelectorConfig(min=2, max=60, step=1, unit_of_measurement="s", mode=sel.NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_FORCE_API, default=cur.get(CONF_FORCE_API, "auto")): _select(
                    ["auto", P.FW_JSON, P.FW_TEXT], CONF_FORCE_API
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_water_heater(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        coordinator = getattr(self.config_entry, "runtime_data", None)
        cfg = coordinator.config if coordinator else None
        if user_input is not None:
            errors = _check_ballon(user_input)
            if not errors:
                data = {CONF_HOST: self.config_entry.data[CONF_HOST], **_clean_ballon(user_input)}
                self.hass.config_entries.async_update_entry(self.config_entry, data=data)
                return self.async_create_entry(title="", data=self._opts)
        return self.async_show_form(
            step_id="water_heater",
            data_schema=_ballon_schema(cfg, user_input or dict(self.config_entry.data)),
            errors=errors,
            description_placeholders={
                "name": cfg.name if cfg else self.config_entry.title,
                "version": cfg.firmware.version if cfg else "?",
                "untested": "",
            },
        )
