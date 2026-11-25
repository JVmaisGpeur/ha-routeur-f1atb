"""Installation et options de l'intégration Routeur F1ATB.

Une question à la fois : chaque écran n'affiche que ce qui est utile selon les réponses
précédentes, et ce que le routeur fournit déjà est prérempli ou déduit.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import discovery_flow, selector as sel
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
)
from .discovery import async_scan

CONF_ROUTERS = "routers"


def _scan_summary(hass, scan, configured: set) -> str:
    """Compte rendu de la recherche, affiché quand aucun nouveau routeur n'est trouvé."""
    lang = str(getattr(getattr(hass, "config", None), "language", "") or "fr")
    nets = ", ".join(scan.networks) or "–"
    already = [h for h in scan.found if h in configured]
    if lang.startswith("fr"):
        txt = f"\n\nRecherche sur {nets} : {scan.tested} adresses testées, {scan.web} serveur(s) web, aucun nouveau routeur F1ATB."
        if already:
            txt += f" Déjà ajouté(s) : {', '.join(already)}."
    else:
        txt = f"\n\nSearch on {nets}: {scan.tested} addresses tested, {scan.web} web server(s), no new F1ATB router."
        if already:
            txt += f" Already added: {', '.join(already)}."
    return txt


async def _probe(hass, host: str) -> tuple[RouterConfig, dict, list]:
    """Lecture seule : version, configuration, système et températures."""
    client = F1atbClient(async_get_clientsession(hass), host)
    await client.async_detect()
    cfg = await client.async_get_config()
    try:
        system = await client.async_get_system()
    except F1atbError:
        system = {}
    try:
        temps = (await client.async_get_live()).get("temperatures") or []
    except F1atbError:
        temps = []
    return cfg, system, temps


def _unique_id(cfg: RouterConfig, system: dict, host: str) -> str:
    if system.get("mac"):
        return format_mac(system["mac"])
    return str(system.get("hostname") or cfg.name or host)


def _active_actions(cfg: RouterConfig) -> list[P.ActionConfig]:
    return [a for a in cfg.actions if a.mode != "inactive"] or list(cfg.actions)


def _action_label(a: P.ActionConfig) -> str:
    return f"{a.title} ({'triac' if a.is_triac else 'relais'})"


def _select(options, key: str | None = None, multiple: bool = False) -> sel.SelectSelector:
    config = sel.SelectSelectorConfig(options=options, multiple=multiple, mode=sel.SelectSelectorMode.LIST)
    if key:
        # Home Assistant refuse translation_key=None (le formulaire répondait « 400 Bad Request »)
        config["translation_key"] = key
    return sel.SelectSelector(config)


def _number(minimum, maximum, step, unit) -> sel.NumberSelector:
    return sel.NumberSelector(
        sel.NumberSelectorConfig(min=minimum, max=maximum, step=step, unit_of_measurement=unit, mode=sel.NumberSelectorMode.BOX)
    )


class _WaterHeaterSteps:
    """Questions sur le chauffe-eau, partagées par l'installation et les options."""

    _cfg: RouterConfig | None
    _temps: list
    _ballon: dict

    def _probes(self) -> list[int]:
        """Sondes du routeur qui donnent une valeur ou portent un nom."""
        names = self._cfg.temp_names if self._cfg else []
        out = []
        for c in range(4):
            has_val = c < len(self._temps) and self._temps[c] is not None
            has_name = c < len(names) and bool(names[c])
            if has_val or has_name:
                out.append(c)
        return out

    def _probe_label(self, c: int) -> str:
        names = self._cfg.temp_names if self._cfg else []
        name = names[c] if c < len(names) and names[c] else f"Sonde {c + 1}"
        val = self._temps[c] if c < len(self._temps) else None
        return f"{name} ({val:.1f} °C)" if val is not None else name

    async def _ballon_done(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_output(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        actions = _active_actions(self._cfg) if self._cfg else []
        if len(actions) <= 1:
            self._ballon[CONF_ACTION] = actions[0].index if actions else 0
            return await self.async_step_temperature()
        if user_input is not None:
            self._ballon[CONF_ACTION] = int(user_input[CONF_ACTION])
            return await self.async_step_temperature()
        opts = [sel.SelectOptionDict(value=str(a.index), label=_action_label(a)) for a in actions]
        default = str(self._ballon.get(CONF_ACTION, actions[0].index))
        return self.async_show_form(
            step_id="output", data_schema=vol.Schema({vol.Required(CONF_ACTION, default=default): _select(opts)})
        )

    async def async_step_temperature(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        probes = self._probes()
        if user_input is not None:
            src = user_input[CONF_TEMP_SOURCE]
            self._ballon[CONF_TEMP_SOURCE] = src
            if src == "router":
                if len(probes) == 1:
                    self._ballon[CONF_TEMP_CHANNEL] = probes[0]
                    self._ballon[CONF_HOT_METHOD] = "temperature"
                    return await self.async_step_power()
                return await self.async_step_temp_channel()
            if src == "entity":
                return await self.async_step_temp_entity()
            return await self.async_step_hot()
        options = (["router"] if probes else []) + ["entity", "none"]
        default = self._ballon.get(CONF_TEMP_SOURCE) or ("router" if probes else "none")
        if default not in options:
            default = options[0]
        return self.async_show_form(
            step_id="temperature",
            data_schema=vol.Schema({vol.Required(CONF_TEMP_SOURCE, default=default): _select(options, CONF_TEMP_SOURCE)}),
            description_placeholders={"probes": ", ".join(self._probe_label(c) for c in probes) or "—"},
        )

    async def async_step_temp_channel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._ballon[CONF_TEMP_CHANNEL] = int(user_input[CONF_TEMP_CHANNEL])
            self._ballon[CONF_HOT_METHOD] = "temperature"
            return await self.async_step_power()
        opts = [sel.SelectOptionDict(value=str(c), label=self._probe_label(c)) for c in self._probes()]
        default = str(self._ballon.get(CONF_TEMP_CHANNEL, opts[0]["value"] if opts else "0"))
        return self.async_show_form(
            step_id="temp_channel", data_schema=vol.Schema({vol.Required(CONF_TEMP_CHANNEL, default=default): _select(opts)})
        )

    async def async_step_temp_entity(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._ballon[CONF_TEMP_ENTITY] = user_input[CONF_TEMP_ENTITY]
            self._ballon[CONF_HOT_METHOD] = "temperature"
            return await self.async_step_power()
        return self.async_show_form(
            step_id="temp_entity",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TEMP_ENTITY, default=self._ballon.get(CONF_TEMP_ENTITY, vol.UNDEFINED)): sel.EntitySelector(
                        sel.EntitySelectorConfig(domain="sensor", device_class="temperature")
                    )
                }
            ),
        )

    async def async_step_hot(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Sans sonde : comment savoir que l'eau est chaude ?"""
        if user_input is not None:
            self._ballon[CONF_HOT_METHOD] = user_input[CONF_HOT_METHOD]
            if user_input[CONF_HOT_METHOD] == "energy":
                return await self.async_step_hot_energy()
            return await self.async_step_power()
        default = self._ballon.get(CONF_HOT_METHOD)
        if default not in ("thermostat", "energy"):
            default = "thermostat"
        return self.async_show_form(
            step_id="hot",
            data_schema=vol.Schema({vol.Required(CONF_HOT_METHOD, default=default): _select(["thermostat", "energy"], CONF_HOT_METHOD)}),
        )

    async def async_step_hot_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._ballon[CONF_HOT_ENERGY] = float(user_input[CONF_HOT_ENERGY])
            return await self.async_step_power()
        return self.async_show_form(
            step_id="hot_energy",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOT_ENERGY, default=self._ballon.get(CONF_HOT_ENERGY, DEFAULT_HOT_ENERGY)): _number(0.5, 20, 0.1, "kWh")}
            ),
        )

    async def async_step_power(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            src = user_input[CONF_POWER_SOURCE]
            self._ballon[CONF_POWER_SOURCE] = src
            if src == "declared":
                return await self.async_step_power_declared()
            if src == "meter":
                return await self.async_step_power_meter()
            return await self._ballon_done()
        default = self._ballon.get(CONF_POWER_SOURCE, "declared")
        return self.async_show_form(
            step_id="power",
            data_schema=vol.Schema(
                {vol.Required(CONF_POWER_SOURCE, default=default): _select(["declared", "meter", "calibration"], CONF_POWER_SOURCE)}
            ),
        )

    async def async_step_power_declared(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._ballon[CONF_DECLARED_POWER] = float(user_input[CONF_DECLARED_POWER])
            return await self._ballon_done()
        return self.async_show_form(
            step_id="power_declared",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DECLARED_POWER, default=self._ballon.get(CONF_DECLARED_POWER, DEFAULT_DECLARED_POWER)): _number(
                        100, 10000, 10, "W"
                    )
                }
            ),
        )

    async def async_step_power_meter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._ballon[CONF_METER_ENTITY] = user_input[CONF_METER_ENTITY]
            return await self._ballon_done()
        return self.async_show_form(
            step_id="power_meter",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_METER_ENTITY, default=self._ballon.get(CONF_METER_ENTITY, vol.UNDEFINED)): sel.EntitySelector(
                        sel.EntitySelectorConfig(domain="sensor", device_class="power")
                    )
                }
            ),
        )

    def _clean_ballon(self) -> dict:
        b = dict(self._ballon)
        src = b.get(CONF_TEMP_SOURCE, "none")
        if src != "router":
            b.pop(CONF_TEMP_CHANNEL, None)
        if src != "entity":
            b.pop(CONF_TEMP_ENTITY, None)
        if src != "none":
            b[CONF_HOT_METHOD] = "temperature"
        if b.get(CONF_HOT_METHOD) != "energy":
            b.pop(CONF_HOT_ENERGY, None)
        if b.get(CONF_POWER_SOURCE) != "meter":
            b.pop(CONF_METER_ENTITY, None)
        b.setdefault(CONF_DECLARED_POWER, DEFAULT_DECLARED_POWER)
        return b


class F1atbConfigFlow(_WaterHeaterSteps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._cfg: RouterConfig | None = None
        self._system: dict = {}
        self._temps: list = []
        self._ballon: dict = {}
        self._found: dict[str, tuple[RouterConfig, dict, list]] = {}

    # ------------------------------------------------ premier écran
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["search", "manual"])

    async def async_step_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Recherche sur le réseau local, puis choix des routeurs à ajouter."""
        if user_input is None:
            configured = {e.data.get(CONF_HOST) for e in self._async_current_entries(include_ignore=False)}
            scan = await async_scan(self.hass)
            self._found = {}
            for host in scan.found:
                if host in configured:
                    continue
                try:
                    self._found[host] = await _probe(self.hass, host)
                except F1atbError:
                    continue
            if not self._found:
                return self._manual_form({"base": "none_found"}, _scan_summary(self.hass, scan, configured))
            opts = [
                sel.SelectOptionDict(value=h, label=f"{cfg.name} – {h} – firmware {cfg.firmware.version}")
                for h, (cfg, _s, _t) in self._found.items()
            ]
            return self.async_show_form(
                step_id="search",
                data_schema=vol.Schema({vol.Required(CONF_ROUTERS, default=[opts[0]["value"]]): _select(opts, multiple=True)}),
                description_placeholders={"count": str(len(opts))},
            )
        chosen = [h for h in user_input.get(CONF_ROUTERS, []) if h in self._found]
        if not chosen:
            return self.async_abort(reason="nothing_selected")
        # Les autres routeurs cochés sont proposés chacun dans « Découverts », avec confirmation
        for other in chosen[1:]:
            discovery_flow.async_create_flow(
                self.hass, DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data={CONF_HOST: other}
            )
        host = chosen[0]
        self._cfg, self._system, self._temps = self._found[host]
        return await self._async_use(host)

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                self._cfg, self._system, self._temps = await _probe(self.hass, host)
            except F1atbError:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_use(host)
        return self._manual_form(errors)

    def _manual_form(self, errors: dict[str, str], scan: str = "") -> ConfigFlowResult:
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
            description_placeholders={"scan": scan},
        )

    async def _async_use(self, host: str) -> ConfigFlowResult:
        assert self._cfg is not None
        self._host = host
        await self.async_set_unique_id(_unique_id(self._cfg, self._system, host))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        return await self.async_step_output()

    # ------------------------------------------------ découverte automatique
    async def async_step_dhcp(self, discovery_info) -> ConfigFlowResult:
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        return await self._async_discovered(discovery_info.ip)

    async def async_step_integration_discovery(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        return await self._async_discovered(discovery_info[CONF_HOST])

    async def _async_discovered(self, host: str) -> ConfigFlowResult:
        self._async_abort_entries_match({CONF_HOST: host})
        try:
            self._cfg, self._system, self._temps = await _probe(self.hass, host)
        except F1atbError:
            return self.async_abort(reason="cannot_connect")
        self._host = host
        await self.async_set_unique_id(_unique_id(self._cfg, self._system, host))
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self.context["title_placeholders"] = {"name": self._cfg.name, "host": host}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._cfg is not None
        if user_input is not None:
            return await self.async_step_output()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._cfg.name,
                "host": str(self._host),
                "version": self._cfg.firmware.version,
                "actions": ", ".join(_action_label(a) for a in _active_actions(self._cfg)) or "—",
            },
        )

    # ------------------------------------------------ fin : heures creuses
    async def _ballon_done(self) -> ConfigFlowResult:
        return await self.async_step_offpeak()

    async def async_step_offpeak(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._cfg is not None
        has_probe = self._ballon.get(CONF_TEMP_SOURCE, "none") != "none"
        if user_input is not None:
            options = {
                CONF_HC_START: user_input[CONF_HC_START],
                CONF_HC_END: user_input[CONF_HC_END],
                CONF_DEADLINE: user_input[CONF_HC_END],
            }
            if has_probe:
                options[CONF_TARGET_TEMP] = float(user_input[CONF_TARGET_TEMP])
            return self.async_create_entry(
                title=self._cfg.name, data={CONF_HOST: self._host, **self._clean_ballon()}, options=options
            )
        schema: dict = {}
        if has_probe:
            schema[vol.Required(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP)] = _number(30, 75, 0.5, "°C")
        schema[vol.Required(CONF_HC_START, default=DEFAULT_HC_START)] = sel.TimeSelector()
        schema[vol.Required(CONF_HC_END, default=DEFAULT_HC_END)] = sel.TimeSelector()
        act = next((a for a in self._cfg.actions if a.index == self._ballon.get(CONF_ACTION)), None)
        has_on = bool(act and any(s.kind == "on" for s in act.slots))
        return self.async_show_form(
            step_id="offpeak",
            data_schema=vol.Schema(schema),
            description_placeholders={"on_slot": "✔" if has_on else "—"},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return F1atbOptionsFlow()


class F1atbOptionsFlow(_WaterHeaterSteps, OptionsFlow):
    """Options en trois rubriques : chauffe-eau, heures creuses et consigne, avancé."""

    def __init__(self) -> None:
        self._cfg = None
        self._temps: list = []
        self._ballon: dict = {}

    def _load(self) -> None:
        coordinator = getattr(self.config_entry, "runtime_data", None)
        self._cfg = coordinator.config if coordinator else None
        self._temps = list(((coordinator.data or {}).get("temperatures") or []) if coordinator else [])
        if not self._ballon:
            self._ballon = {k: v for k, v in self.config_entry.data.items() if k != CONF_HOST}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        self._load()
        return self.async_show_menu(step_id="init", menu_options=["output", "offpeak", "advanced"])

    async def _ballon_done(self) -> ConfigFlowResult:
        data = {CONF_HOST: self.config_entry.data[CONF_HOST], **self._clean_ballon()}
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
        return self.async_create_entry(title="", data=dict(self.config_entry.options))

    async def async_step_offpeak(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        cur = {**self.config_entry.data, **self.config_entry.options}
        has_probe = self.config_entry.data.get(CONF_TEMP_SOURCE, "none") != "none"
        if user_input is not None:
            opts = dict(self.config_entry.options)
            opts.pop(CONF_HC_ENTITY, None)
            opts.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_create_entry(title="", data=opts)
        schema: dict = {}
        if has_probe:
            schema[vol.Required(CONF_TARGET_TEMP, default=cur.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP))] = _number(30, 75, 0.5, "°C")
            schema[vol.Required(CONF_HYSTERESIS, default=cur.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS))] = _number(0.5, 10, 0.5, "°C")
        schema[vol.Required(CONF_HC_START, default=cur.get(CONF_HC_START, DEFAULT_HC_START))] = sel.TimeSelector()
        schema[vol.Required(CONF_HC_END, default=cur.get(CONF_HC_END, DEFAULT_HC_END))] = sel.TimeSelector()
        schema[vol.Required(CONF_DEADLINE, default=cur.get(CONF_DEADLINE, cur.get(CONF_HC_END, DEFAULT_HC_END)))] = sel.TimeSelector()
        schema[vol.Optional(CONF_HC_ENTITY, description={"suggested_value": cur.get(CONF_HC_ENTITY)})] = sel.EntitySelector(
            sel.EntitySelectorConfig(domain=["binary_sensor", "input_boolean", "switch"])
        )
        return self.async_show_form(step_id="offpeak", data_schema=vol.Schema(schema))

    async def async_step_advanced(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        cur = {**self.config_entry.data, **self.config_entry.options}
        if user_input is not None:
            opts = dict(self.config_entry.options)
            opts.pop(CONF_GRID_ENTITY, None)
            opts.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_create_entry(title="", data=opts)
        schema = {
            vol.Required(CONF_ALLOW_EXTERNAL, default=cur.get(CONF_ALLOW_EXTERNAL, True)): sel.BooleanSelector(),
            vol.Required(CONF_MAX_MANUAL_MIN, default=cur.get(CONF_MAX_MANUAL_MIN, DEFAULT_MAX_MANUAL_MIN)): _number(30, 1440, 30, "min"),
            vol.Optional(CONF_GRID_ENTITY, description={"suggested_value": cur.get(CONF_GRID_ENTITY)}): sel.EntitySelector(
                sel.EntitySelectorConfig(domain="sensor", device_class="power")
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): _number(2, 60, 1, "s"),
            vol.Required(CONF_FORCE_API, default=cur.get(CONF_FORCE_API, "auto")): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=["auto", P.FW_JSON, P.FW_TEXT], translation_key=CONF_FORCE_API, mode=sel.SelectSelectorMode.DROPDOWN
                )
            ),
        }
        if self.config_entry.data.get(CONF_TEMP_SOURCE, "none") != "none":
            schema[vol.Required(CONF_SAFETY_TEMP, default=cur.get(CONF_SAFETY_TEMP, DEFAULT_SAFETY_TEMP))] = _number(50, 85, 1, "°C")
        return self.async_show_form(step_id="advanced", data_schema=vol.Schema(schema))
