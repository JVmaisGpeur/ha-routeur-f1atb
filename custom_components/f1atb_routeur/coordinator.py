"""Coordinateur : lecture du routeur, calculs et logique de pilotage.

Toute la logique tient ici :
- lecture des mesures (chaque cycle), du système (chaque minute), de la configuration
  et du planning (toutes les 5 minutes, et dès qu'on le demande) ;
- puissance routée (mesurée par un compteur dédié, sinon estimée), énergies du jour ;
- température du ballon, détection du thermostat, « ballon chaud » ;
- modes autonomes (Arrêt, Solaire seul, Solaire + garantie, Marche forcée) ;
- pilotage externe générique (prise de main qui expire au bout de 30 min) ;
- sécurité thermique.
Les seules commandes envoyées au routeur sont des forçages temporaires de 30 min,
décomptés par le routeur lui-même : si Home Assistant s'arrête, le routeur reprend
seul son planning au plus tard 30 min après.
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parsers as P
from .api import F1atbClient, F1atbError, RouterConfig
from .const import (
    ALL_MODES,
    CONF_ACTION,
    CONF_ALLOW_EXTERNAL,
    CONF_DEADLINE,
    CONF_DECLARED_POWER,
    CONF_FORCE_API,
    CONF_GRID_ENTITY,
    CONF_HC_END,
    CONF_HC_ENTITY,
    CONF_HC_START,
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
    EVENT_EXTERNAL_EXPIRED,
    EVENT_TARGET_MISSED,
    EVENT_THERMOSTAT,
    EXTERNAL_KEYS,
    EXTERNAL_TIMEOUT_S,
    FORCE_CHUNK_MIN,
    FORCE_RENEW_BELOW_MIN,
    MODE_EXTERNAL,
    MODE_FORCED,
    MODE_GUARANTEE,
    MODE_OFF,
    MODE_SOLAR,
    STORAGE_VERSION,
    THERMO_HOLD_S,
    THERMO_JUMP_RATIO,
    THERMO_METER_RATIO,
    THERMO_OPEN_MIN,
    USER_MODES,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_EVERY_S = 300
SYSTEM_EVERY_S = 60
SAVE_EVERY_S = 300


def _opt(entry: ConfigEntry, key: str, default: Any = None) -> Any:
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


def _parse_time(value: Any, default: str) -> time:
    for raw in (value, default):
        try:
            parts = [int(x) for x in str(raw).split(":")[:2]]
            return time(parts[0], parts[1])
        except (TypeError, ValueError, IndexError):
            continue
    return time(0, 0)


def _in_window(now: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end


class F1atbCoordinator(DataUpdateCoordinator[dict]):
    """Un coordinateur par routeur."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: F1atbClient) -> None:
        scan = int(_opt(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=max(2, scan)),
        )
        self.entry = entry
        self.client = client
        self.config: RouterConfig | None = None
        self.system: dict = {}
        self.read_only = False
        self.read_only_reason: str | None = None
        self.action_index: int = int(entry.data.get(CONF_ACTION, 0))

        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.state: dict[str, Any] = {}
        self._last_config_at: datetime | None = None
        self._last_system_at: datetime | None = None
        self._last_save_at: datetime | None = None
        self._last_sample: tuple[datetime, float] | None = None
        self._net_history: deque[tuple[datetime, float | None, int | None]] = deque(maxlen=6)
        self._meter_low_since: datetime | None = None
        self._commanded: str | None = None  # "on" / "off" / None : forçage posé par nous
        self._deadline_done_for: str | None = None
        self.calibrating = False
        self.last_error: str | None = None

    # ------------------------------------------------------------------ stockage
    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        defaults = {
            "mode": None,
            "prev_mode": MODE_GUARANTEE,
            "manual_until": None,
            "target_temp": float(_opt(self.entry, CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)),
            "power_w": float(self.entry.data.get(CONF_DECLARED_POWER) or DEFAULT_DECLARED_POWER),
            "power_origin": "declared",
            "energy_total_kwh": 0.0,
            "energy_today_kwh": 0.0,
            "grid_today_kwh": 0.0,
            "day": dt_util.now().date().isoformat(),
            "hot_day": None,
            "thermostat_open": False,
            "boost": None,
            "external": None,
            "control_enabled": True,
        }
        defaults.update(stored)
        self.state = defaults

    async def async_save(self) -> None:
        self._last_save_at = dt_util.utcnow()
        await self._store.async_save(self.state)

    # ------------------------------------------------------------------ propriétés
    @property
    def power_source(self) -> str:
        return self.entry.data.get(CONF_POWER_SOURCE, "declared")

    @property
    def hot_method(self) -> str:
        method = self.entry.data.get(CONF_HOT_METHOD)
        if method:
            return method
        return "temperature" if self.entry.data.get(CONF_TEMP_SOURCE, "none") != "none" else "thermostat"

    @property
    def ballon_power_w(self) -> float:
        return float(self.state.get("power_w") or DEFAULT_DECLARED_POWER)

    @property
    def safety_temp(self) -> float:
        return float(_opt(self.entry, CONF_SAFETY_TEMP, DEFAULT_SAFETY_TEMP))

    @property
    def action_config(self) -> P.ActionConfig | None:
        if not self.config:
            return None
        for a in self.config.actions:
            if a.index == self.action_index:
                return a
        return None

    @property
    def external(self) -> dict | None:
        ext = self.state.get("external")
        if not ext:
            return None
        if dt_util.utcnow().timestamp() >= float(ext.get("expires_ts", 0)):
            return None
        return ext

    @property
    def control_enabled(self) -> bool:
        """« Piloter le routeur » (True) ou « Affichage seulement » (False)."""
        return bool(self.state.get("control_enabled", True))

    def _require_control(self) -> None:
        if not self.control_enabled:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="control_disabled")

    @property
    def user_mode(self) -> str:
        mode = self.state.get("mode")
        return mode if mode in USER_MODES else self._default_mode()

    @property
    def effective_mode(self) -> str:
        ext = self.external
        if ext and "mode" in ext.get("keys", []):
            return MODE_EXTERNAL
        return self.user_mode

    @property
    def target_temp(self) -> float:
        ext = self.external
        if ext and "target_temperature" in ext.get("keys", []) and ext.get("target_temperature") is not None:
            return float(ext["target_temperature"])
        return float(self.state.get("target_temp") or DEFAULT_TARGET_TEMP)

    def _default_mode(self) -> str:
        """« Solaire seul » si le planning fait déjà un rattrapage (plage ON), sinon garantie."""
        act = self.action_config
        if act and any(s.kind == "on" for s in act.slots):
            return MODE_SOLAR
        return MODE_GUARANTEE

    # ------------------------------------------------------------------ cycle
    async def _async_update_data(self) -> dict:
        now = dt_util.utcnow()
        try:
            if self.config is None or self._due(self._last_config_at, CONFIG_EVERY_S, now):
                await self._async_read_config()
            live = await self.client.async_get_live()
            if self._due(self._last_system_at, SYSTEM_EVERY_S, now):
                try:
                    self.system = await self.client.async_get_system()
                except F1atbError as err:
                    _LOGGER.debug("Système illisible : %s", err)
                self._last_system_at = now
        except F1atbError as err:
            self._last_sample = None
            raise UpdateFailed(str(err)) from err

        data = self._compute(live)
        try:
            await self._async_control(data)
        except F1atbError as err:
            self.last_error = str(err)
            _LOGGER.warning("Commande de forçage refusée par le routeur : %s", err)
        data["status"], data["status_info"] = self._status(data)
        if self._due(self._last_save_at, SAVE_EVERY_S, now):
            await self.async_save()
        return data

    @staticmethod
    def _due(last: datetime | None, every: int, now: datetime) -> bool:
        return last is None or (now - last).total_seconds() >= every

    async def async_refresh_config(self) -> None:
        self._last_config_at = None
        await self.async_request_refresh()

    async def _async_read_config(self) -> None:
        forced = _opt(self.entry, CONF_FORCE_API, "auto")
        if forced in (P.FW_JSON, P.FW_TEXT) and self.client.firmware is None:
            self.client.firmware = P.FirmwareInfo(forced, "?")
        if self.client.firmware is None:
            await self.client.async_detect()
        self.config = await self.client.async_get_config()
        self._last_config_at = dt_util.utcnow()
        fw = self.config.firmware
        manual = forced in (P.FW_JSON, P.FW_TEXT)
        if not fw.tested and not manual:
            self.read_only = True
            self.read_only_reason = f"firmware {fw.version}"
            ir.async_create_issue(
                self.hass, DOMAIN, f"untested_firmware_{self.entry.entry_id}",
                is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="untested_firmware",
                translation_placeholders={"name": self.config.name, "version": fw.version},
            )
        else:
            self.read_only = False
            self.read_only_reason = None
            ir.async_delete_issue(self.hass, DOMAIN, f"untested_firmware_{self.entry.entry_id}")

    # ------------------------------------------------------------------ calculs
    def _state_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if st is None or st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            return None
        try:
            val = float(st.state)
        except ValueError:
            return None
        unit = str(st.attributes.get("unit_of_measurement") or "")
        if unit == "kW":
            val *= 1000
        return val

    def _compute(self, live: dict) -> dict:
        now = dt_util.now()
        today = now.date().isoformat()
        if self.state.get("day") != today:
            self.state.update(day=today, energy_today_kwh=0.0, grid_today_kwh=0.0)
            self.state["thermostat_open"] = False
            self._deadline_done_for = None

        act_live = (live.get("actions") or {}).get(self.action_index) or {}
        act_cfg = self.action_config
        opening = act_live.get("opening")
        force_min = int(act_live.get("force_min") or 0)
        on_off = bool(act_cfg and act_cfg.on_off)

        # -- température du ballon
        temp = None
        src = self.entry.data.get(CONF_TEMP_SOURCE, "none")
        if src == "router":
            ch = int(self.entry.data.get(CONF_TEMP_CHANNEL, 0))
            temps = live.get("temperatures") or []
            temp = temps[ch] if ch < len(temps) else None
        elif src == "entity":
            temp = self._state_float(self.entry.data.get(CONF_TEMP_ENTITY))

        # -- réseau (pour la calibration et la détection du thermostat)
        grid_net = self._state_float(_opt(self.entry, CONF_GRID_ENTITY))
        if grid_net is None:
            grid_net = live.get("grid_net_w")

        # -- puissance routée : mesurée (compteur dédié) ou estimée
        meter = None
        if self.power_source == "meter":
            meter = self._state_float(self.entry.data.get(CONF_METER_ENTITY))
            if meter is not None and (opening or 0) >= 95 and meter > 100:
                learned = max(meter, self.ballon_power_w * 0.9) if self.state.get("power_origin") == "meter" else meter
                self.state["power_w"] = round(learned)
                self.state["power_origin"] = "meter"
        self._detect_thermostat(now, opening, grid_net, meter)
        if meter is not None:
            routed = max(0.0, meter)
            measured = True
        else:
            measured = False
            if opening is None:
                routed = 0.0
            elif self.state.get("thermostat_open"):
                routed = 0.0
            elif on_off:
                routed = self.ballon_power_w if opening > 0 else 0.0
            else:
                routed = self.ballon_power_w * max(0, min(100, opening)) / 100

        # -- créneau du planning en cours
        slot = None
        if act_cfg:
            slot = P.slot_at(act_cfg.slots, now.hour * 60 + now.minute)

        # -- énergies (méthode des trapèzes)
        ts = dt_util.utcnow()
        if self._last_sample is not None:
            t0, p0 = self._last_sample
            dt_h = (ts - t0).total_seconds() / 3600
            if 0 < dt_h < 0.1:
                kwh = (p0 + routed) / 2 * dt_h / 1000
                self.state["energy_total_kwh"] = float(self.state.get("energy_total_kwh") or 0) + kwh
                self.state["energy_today_kwh"] = float(self.state.get("energy_today_kwh") or 0) + kwh
                grid_part = force_min > 0 or (slot is not None and slot.kind == "on")
                if grid_part:
                    self.state["grid_today_kwh"] = float(self.state.get("grid_today_kwh") or 0) + kwh
        self._last_sample = (ts, routed)

        reached = self._is_hot(temp)
        if reached and self.state.get("hot_day") != today:
            self.state["hot_day"] = today

        ext = self.external
        if self.state.get("external") and ext is None:
            expired = self.state["external"]
            self.state["external"] = None
            self.hass.bus.async_fire(
                EVENT_EXTERNAL_EXPIRED,
                {"device_id": self.device_id, "controller": expired.get("controller")},
            )
            _LOGGER.info("Pilotage externe par %s expiré : retour au mode %s", expired.get("controller"), self.user_mode)

        return {
            "connected": True,
            "firmware": self.config.firmware.version if self.config else None,
            "firmware_api": self.config.firmware.api if self.config else None,
            "router_name": self.config.name if self.config else None,
            "tariff": live.get("tariff"),
            "temperatures": live.get("temperatures"),
            "temp_names": self.config.temp_names if self.config else [],
            "water_temperature": temp,
            "opening": opening,
            "force_min": force_min,
            "on_off": on_off,
            "is_triac": bool(act_cfg and act_cfg.is_triac),
            "routed_power_w": round(routed, 1),
            "routed_measured": measured,
            "grid_net_w": grid_net,
            "slot": slot.as_dict() if slot else None,
            "slots": [s.as_dict() for s in act_cfg.slots] if act_cfg else [],
            "action_title": act_cfg.title if act_cfg else None,
            "action_mode": act_cfg.mode if act_cfg else None,
            "force_opening": act_cfg.force_opening if act_cfg else None,
            "reached": reached,
            "thermostat_open": bool(self.state.get("thermostat_open")),
            "external": ext,
            "system": self.system,
            "desired": None,
            "reason": None,
            "boost_active": False,
        }

    def _detect_thermostat(self, now: datetime, opening: int | None, grid_net: float | None, meter: float | None) -> None:
        """Coupure du thermostat : compteur dédié à ~0 W, ou saut d'injection au compteur
        de l'ordre de la puissance du ballon alors que la sortie reste ouverte."""
        was = bool(self.state.get("thermostat_open"))
        is_open = was
        if meter is not None:
            if (opening or 0) >= THERMO_OPEN_MIN and meter < self.ballon_power_w * THERMO_METER_RATIO:
                self._meter_low_since = self._meter_low_since or now
                if (now - self._meter_low_since).total_seconds() >= THERMO_HOLD_S:
                    is_open = True
            else:
                self._meter_low_since = None
                if (opening or 0) >= THERMO_OPEN_MIN and meter >= self.ballon_power_w * 0.5:
                    is_open = False
        else:
            self._net_history.append((now, grid_net, opening))
            pts = [p for p in self._net_history if p[1] is not None and p[2] is not None]
            if len(pts) >= 3:
                (_, n0, o0), (_, n1, o1), (_, n2, o2) = pts[-3], pts[-2], pts[-1]
                jump = self.ballon_power_w * THERMO_JUMP_RATIO
                steady = min(o0, o1, o2) >= THERMO_OPEN_MIN
                if steady and (n0 - n2) >= jump:
                    is_open = True  # la consommation chute d'un coup, sortie toujours ouverte
                elif steady and (n2 - n0) >= jump:
                    is_open = False  # le thermostat se referme
                elif o0 < 30 and min(o1, o2) >= THERMO_OPEN_MIN:
                    # Mise en marche : la consommation doit monter d'au moins la moitié
                    # de la puissance du ballon, sinon le thermostat est déjà coupé
                    is_open = (n2 - n0) < self.ballon_power_w * 0.5
        if is_open != was:
            self.state["thermostat_open"] = is_open
            if is_open:
                self.hass.bus.async_fire(EVENT_THERMOSTAT, {"device_id": self.device_id})

    def _is_hot(self, temp: float | None) -> bool:
        method = self.hot_method
        if method == "temperature":
            return temp is not None and temp >= self.target_temp
        if method == "energy":
            return float(self.state.get("energy_today_kwh") or 0) >= float(
                self.entry.data.get(CONF_HOT_ENERGY, DEFAULT_HOT_ENERGY)
            )
        return bool(self.state.get("thermostat_open")) or self.state.get("hot_day") == dt_util.now().date().isoformat()

    def _needs_heat(self, temp: float | None) -> bool:
        """Faut-il chauffer ? (avec hystérésis en mode température)."""
        if self.hot_method == "temperature":
            if temp is None:
                return False  # sonde absente : pas de rattrapage (sécurité)
            hyst = float(_opt(self.entry, CONF_HYSTERESIS, DEFAULT_HYSTERESIS))
            boost = self.state.get("boost")
            limit = self.target_temp if boost else self.target_temp - hyst
            return temp < limit
        return not self._is_hot(temp)

    # ------------------------------------------------------------------ pilotage
    def _offpeak(self, now: datetime) -> bool:
        """Fenêtre de rattrapage : heures creuses ET entre leur début et l'heure limite.

        Avec une entité « heures creuses » qui reste active tout le week-end, le
        rattrapage ne démarre donc pas en pleine journée avant le soleil."""
        start = _parse_time(_opt(self.entry, CONF_HC_START), DEFAULT_HC_START)
        end = _parse_time(_opt(self.entry, CONF_HC_END), DEFAULT_HC_END)
        deadline = _parse_time(_opt(self.entry, CONF_DEADLINE), DEFAULT_DEADLINE)
        ent = _opt(self.entry, CONF_HC_ENTITY)
        if ent:
            st = self.hass.states.get(ent)
            if st is None or st.state != STATE_ON:
                return False
            return _in_window(now.time(), start, deadline) if start != deadline else True
        return _in_window(now.time(), start, end) and (
            _in_window(now.time(), start, deadline) if start != deadline else True
        )

    def _desired(self, data: dict) -> tuple[str | None, str]:
        """Forçage voulu (« on », « off » ou None = laisser le planning) et sa raison."""
        now = dt_util.now()
        temp = data.get("water_temperature")
        mode = self.effective_mode
        ext = self.external
        sub_mode = (ext or {}).get("mode") if mode == MODE_EXTERNAL else mode

        # Fin d'une marche forcée manuelle
        until = self.state.get("manual_until")
        if self.user_mode == MODE_FORCED and until and now.timestamp() >= float(until):
            self.state["mode"] = self.state.get("prev_mode") or self._default_mode()
            self.state["manual_until"] = None
            if mode != MODE_EXTERNAL:
                sub_mode = self.state["mode"]

        boost = self._update_boost(now, temp, data)

        desired: str | None = None
        reason = sub_mode or MODE_SOLAR
        if sub_mode == MODE_OFF:
            desired, reason = "off", "off"
        elif sub_mode == MODE_FORCED:
            desired, reason = "on", "forced"
        elif boost:
            desired, reason = "on", "boost"
        elif sub_mode == MODE_GUARANTEE and self._offpeak(now) and self._needs_heat(temp):
            self.state["boost"] = {"kind": "auto", "started": now.timestamp()}
            desired, reason = "on", "boost"

        # Échéance de garantie : prévenir si le ballon n'est pas chaud
        if sub_mode == MODE_GUARANTEE:
            deadline = _parse_time(_opt(self.entry, CONF_DEADLINE), DEFAULT_DEADLINE)
            today = now.date().isoformat()
            if (
                self._deadline_done_for != today
                and now.time() >= deadline
                and (now - timedelta(minutes=10)).time() < deadline
            ):
                self._deadline_done_for = today
                if not data.get("reached"):
                    self.hass.bus.async_fire(
                        EVENT_TARGET_MISSED,
                        {"device_id": self.device_id, "temperature": temp, "target": self.target_temp},
                    )

        # Sécurité thermique : jamais de marche forcée au-delà de la température de sécurité
        if desired == "on" and temp is not None and temp >= self.safety_temp:
            desired, reason = None, "safety"
            self.state["boost"] = None
        return desired, reason

    def _update_boost(self, now: datetime, temp: float | None, data: dict) -> bool:
        boost = self.state.get("boost")
        if not boost:
            return False
        done = False
        kind = boost.get("kind")
        if kind == "auto":
            if not self._offpeak(now) or not self._needs_heat(temp) or self.effective_mode not in (
                MODE_GUARANTEE, MODE_EXTERNAL
            ):
                done = True
        else:
            if boost.get("until_ts") and now.timestamp() >= float(boost["until_ts"]):
                done = True
            if boost.get("until_temperature") is not None and temp is not None and temp >= float(boost["until_temperature"]):
                done = True
            if boost.get("energy_kwh") is not None:
                start_e = float(boost.get("start_energy", 0))
                if float(self.state.get("energy_total_kwh") or 0) - start_e >= float(boost["energy_kwh"]):
                    done = True
            if boost.get("until_hot") and data.get("reached"):
                done = True
        if done:
            self.state["boost"] = None
            return False
        return True

    async def _async_control(self, data: dict) -> None:
        if not self.control_enabled:
            # Affichage seulement : on lève une seule fois un forçage posé par nous, puis plus rien
            force = int(data.get("force_min") or 0)
            if self._commanded is not None and force != 0 and self.action_config:
                await self.client.async_force(self.action_index, 0, force)
            self._commanded = None
            data["desired"], data["reason"] = None, "display_only"
            return
        if self.read_only or self.calibrating or not self.action_config:
            data["desired"], data["reason"] = None, "read_only" if self.read_only else "idle"
            return
        desired, reason = self._desired(data)
        data["desired"], data["reason"] = desired, reason
        data["boost_active"] = reason == "boost"
        force = int(data.get("force_min") or 0)
        idx = self.action_index
        if desired == "on":
            if force < FORCE_RENEW_BELOW_MIN:  # rien, presque fini, ou arrêt forcé à remplacer
                await self.client.async_force(idx, FORCE_CHUNK_MIN, force)
                self._commanded = "on"
        elif desired == "off":
            if force > -FORCE_RENEW_BELOW_MIN:
                await self.client.async_force(idx, -FORCE_CHUNK_MIN, force)
                self._commanded = "off"
        elif self._commanded is not None:
            if force != 0:
                await self.client.async_force(idx, 0, force)
            self._commanded = None

    def _status(self, data: dict) -> tuple[str, dict]:
        """État lisible par la carte et les automatisations (capteur « status »)."""
        now = dt_util.now()
        ext = data.get("external")
        slot = data.get("slot") or {}
        force = int(data.get("force_min") or 0)
        power = float(data.get("routed_power_w") or 0)
        reason = data.get("reason")
        info: dict[str, Any] = {
            "power_w": round(power),
            "temperature": data.get("water_temperature"),
            "target": self.target_temp,
            "controller": (ext or {}).get("controller"),
            "reason": (ext or {}).get("reason"),
            "slot_kind": slot.get("kind"),
            "slot_end": slot.get("end"),
            "force_min": force,
            "until": None,
        }
        if ext:
            info["until"] = datetime.fromtimestamp(float(ext["expires_ts"]), tz=dt_util.UTC).isoformat()
        # Affichage seulement / lecture seule : on décrit quand même ce que fait le routeur
        info["display_only"] = not self.control_enabled
        info["read_only"] = self.read_only
        if reason == "safety":
            return "safety", info
        if ext and data.get("desired") == "off":
            return "blocked", info
        if reason == "boost":
            return "boost", info
        if reason == "forced" or (force > 0 and data.get("desired") is None):
            until = self.state.get("manual_until")
            if reason == "forced" and until and self.effective_mode != MODE_EXTERNAL:
                info["until"] = datetime.fromtimestamp(float(until), tz=dt_util.UTC).isoformat()
            elif force > 0:
                info["until"] = (now + timedelta(minutes=force)).isoformat()
            return "forced", info
        if data.get("desired") == "off" or force < 0:
            return "off", info
        if slot.get("kind") == "on" and power > 0:
            return "on_slot", info
        if power > 0:
            return "solar", info
        if data.get("reached"):
            return "hot", info
        if slot.get("kind") == "route":
            return "waiting_surplus", info
        return "idle", info

    # ------------------------------------------------------------------ actions
    @property
    def device_id(self) -> str | None:
        from homeassistant.helpers import device_registry as dr

        reg = dr.async_get(self.hass)
        dev = reg.async_get_device(identifiers={(DOMAIN, self.entry.unique_id or self.entry.entry_id)})
        return dev.id if dev else None

    def _check_owner(self, key: str, controller: str | None, override: bool) -> None:
        ext = self.external
        if not ext or key not in ext.get("keys", []):
            if controller and not override:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="not_controller",
                    translation_placeholders={"controller": controller},
                )
            return
        if controller and controller == ext.get("controller"):
            return
        if override:
            _LOGGER.info("Action de l'utilisateur prioritaire : fin du pilotage par %s", ext.get("controller"))
            self.state["external"] = None
            return
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="externally_controlled",
            translation_placeholders={"controller": str(ext.get("controller"))},
        )

    async def async_set_mode(
        self,
        mode: str,
        *,
        duration_min: int | None = None,
        controller: str | None = None,
        override: bool = False,
        reason: str | None = None,
    ) -> None:
        self._require_control()
        if mode not in ALL_MODES or mode == MODE_EXTERNAL:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_mode")
        self._check_owner("mode", controller, override)
        ext = self.external
        if controller and ext and controller == ext.get("controller"):
            if mode == MODE_GUARANTEE:
                mode = MODE_SOLAR  # un pilote décide lui-même des rattrapages
            ext["mode"] = mode
            if reason is not None:
                ext["reason"] = reason[:80] or None
        else:
            if mode == MODE_FORCED:
                max_min = int(_opt(self.entry, CONF_MAX_MANUAL_MIN, DEFAULT_MAX_MANUAL_MIN))
                minutes = max(1, min(int(duration_min or max_min), max_min))
                if self.user_mode != MODE_FORCED:
                    self.state["prev_mode"] = self.user_mode
                self.state["manual_until"] = dt_util.now().timestamp() + minutes * 60
            else:
                self.state["manual_until"] = None
            self.state["mode"] = mode
            if mode != MODE_GUARANTEE and (self.state.get("boost") or {}).get("kind") == "auto":
                self.state["boost"] = None
        await self.async_save()
        await self.async_request_refresh()

    async def async_boost(
        self,
        *,
        duration_min: int | None = None,
        energy_kwh: float | None = None,
        until_temperature: float | None = None,
        controller: str | None = None,
        override: bool = False,
    ) -> None:
        self._require_control()
        self._check_owner("boost", controller, override)
        boost: dict[str, Any] = {"kind": "manual", "started": dt_util.now().timestamp(), "controller": controller}
        if duration_min:
            boost["until_ts"] = dt_util.now().timestamp() + int(duration_min) * 60
        if energy_kwh:
            boost["energy_kwh"] = float(energy_kwh)
            boost["start_energy"] = float(self.state.get("energy_total_kwh") or 0)
        if until_temperature is not None:
            boost["until_temperature"] = float(until_temperature)
        if not (duration_min or energy_kwh or until_temperature is not None):
            boost["until_hot"] = True
            boost["until_ts"] = dt_util.now().timestamp() + 4 * 3600
        self.state["boost"] = boost
        await self.async_save()
        await self.async_request_refresh()

    async def async_cancel_boost(self, *, controller: str | None = None, override: bool = False) -> None:
        self._check_owner("boost", controller, override)
        self.state["boost"] = None
        await self.async_save()
        await self.async_request_refresh()

    async def async_set_target(self, value: float, *, controller: str | None = None, override: bool = False) -> None:
        ext = self.external
        if controller and ext and controller == ext.get("controller") and "target_temperature" in ext.get("keys", []):
            ext["target_temperature"] = float(value)
        else:
            self._check_owner("target_temperature", controller, override)
            self.state["target_temp"] = float(value)
        await self.async_save()
        await self.async_request_refresh()

    async def async_set_control_enabled(self, enabled: bool) -> None:
        """Interrupteur control_enabled : à l'arrêt, plus aucune commande vers le routeur."""
        self.state["control_enabled"] = bool(enabled)
        if not enabled:
            if self.state.get("external"):
                _LOGGER.info("Affichage seulement : fin du pilotage par %s", self.state["external"].get("controller"))
            self.state["external"] = None
            self.state["boost"] = None
        await self.async_save()
        await self.async_request_refresh()

    async def async_set_power(self, value: float, origin: str = "declared") -> None:
        self.state["power_w"] = float(value)
        self.state["power_origin"] = origin
        await self.async_save()
        await self.async_request_refresh()

    async def async_set_force_opening(self, value: float) -> None:
        """Réglage utilisateur uniquement : jamais appelé par le pilotage automatique."""
        self._require_control()
        if not self.config or self.config.firmware.api != P.FW_JSON:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="needs_v17")
        if self.read_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="read_only",
                translation_placeholders={"reason": str(self.read_only_reason)},
            )
        try:
            await self.client.async_set_force_opening(self.action_index, int(value))
        except F1atbError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="write_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_refresh_config()

    async def async_set_external_control(
        self, active: bool, controller: str, keys: list[str] | None, reason: str | None = None
    ) -> None:
        if active:
            self._require_control()
        if not _opt(self.entry, CONF_ALLOW_EXTERNAL, True):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="external_disabled")
        if self.read_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="read_only",
                translation_placeholders={"reason": str(self.read_only_reason)},
            )
        current = self.external
        if not active:
            if current and current.get("controller") == controller:
                self.state["external"] = None
        else:
            if current and current.get("controller") != controller:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="externally_controlled",
                    translation_placeholders={"controller": str(current.get("controller"))},
                )
            keys = [k for k in (keys or EXTERNAL_KEYS) if k in EXTERNAL_KEYS] or list(EXTERNAL_KEYS)
            ext = current or {"controller": controller, "mode": MODE_SOLAR, "since": dt_util.utcnow().isoformat()}
            ext.update(
                controller=controller,
                keys=keys,
                expires_ts=dt_util.utcnow().timestamp() + EXTERNAL_TIMEOUT_S,
            )
            if reason is not None:
                ext["reason"] = reason[:80] or None
            self.state["external"] = ext
        await self.async_save()
        await self.async_request_refresh()

    async def async_calibrate(self) -> None:
        """Mesure la puissance du ballon : écart au compteur pendant un court forçage."""
        if self.calibrating:
            return
        self._require_control()
        if self.read_only:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="read_only",
                translation_placeholders={"reason": str(self.read_only_reason)},
            )
        if self.external:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="externally_controlled",
                translation_placeholders={"controller": str(self.external.get("controller"))},
            )
        self.calibrating = True
        self.async_update_listeners()
        idx = self.action_index
        notif = f"{DOMAIN}_calibration_{self.entry.entry_id}"
        try:
            before = await self._avg_grid()
            live = await self.client.async_get_live()
            force = int(((live.get("actions") or {}).get(idx) or {}).get("force_min") or 0)
            fw = self.client.firmware
            await self.client.async_force(idx, 1 if fw and fw.api == P.FW_JSON else FORCE_CHUNK_MIN, force)
            await asyncio.sleep(8)
            after = await self._avg_grid()
            live = await self.client.async_get_live()
            force = int(((live.get("actions") or {}).get(idx) or {}).get("force_min") or 0)
            await self.client.async_force(idx, 0, force)
            frac = 1.0
            act = self.action_config
            if act and act.force_opening and fw and fw.api == P.FW_JSON:
                frac = max(0.05, act.force_opening / 100)
            if before is None or after is None:
                delta = None
            else:
                delta = (after - before) / frac
            if delta is None or delta < 100:
                persistent_notification.async_create(
                    self.hass,
                    (
                        "La calibration n'a pas vu le chauffe-eau consommer au compteur "
                        f"({'aucune mesure' if delta is None else f'{delta:.0f} W'}). "
                        "Ballon déjà chaud, batteries qui compensent la consommation, ou nuages ? "
                        "La puissance n'a pas été modifiée. / Calibration saw no consumption: "
                        "power left unchanged."
                    ),
                    title="Routeur F1ATB",
                    notification_id=notif,
                )
            else:
                persistent_notification.async_dismiss(self.hass, notif)
                self.state["power_w"] = round(delta)
                self.state["power_origin"] = "calibration"
                await self.async_save()
        finally:
            self.calibrating = False
            self._last_sample = None
            await self.async_request_refresh()

    async def _avg_grid(self) -> float | None:
        vals = []
        ent = _opt(self.entry, CONF_GRID_ENTITY)
        for _ in range(3):
            val = self._state_float(ent) if ent else None
            if val is None:
                live = await self.client.async_get_live()
                val = live.get("grid_net_w")
            if val is not None:
                vals.append(val)
            await asyncio.sleep(2)
        return sum(vals) / len(vals) if vals else None
