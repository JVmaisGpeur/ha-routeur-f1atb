"""Constantes de l'intégration Routeur F1ATB."""
from __future__ import annotations

DOMAIN = "f1atb_routeur"
MANUFACTURER = "F1ATB"
CARD_FILENAME = "f1atb-routeur-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

# --- données de l'entrée (installation)
CONF_HOST = "host"
CONF_ACTION = "water_heater_action"  # index de l'action qui alimente le ballon
CONF_TEMP_SOURCE = "temp_source"  # "none" | "router" | "entity"
CONF_TEMP_CHANNEL = "temp_channel"  # canal 0-3 du routeur
CONF_TEMP_ENTITY = "temp_entity"
CONF_POWER_SOURCE = "power_source"  # "declared" | "meter" | "calibration"
CONF_DECLARED_POWER = "declared_power"
CONF_METER_ENTITY = "meter_entity"
CONF_HOT_METHOD = "hot_method"  # "temperature" | "thermostat" | "energy"
CONF_HOT_ENERGY = "hot_energy_kwh"

# --- options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_GRID_ENTITY = "grid_entity"  # capteur HA de puissance réseau (facultatif)
CONF_HC_ENTITY = "offpeak_entity"  # binary_sensor heures creuses (facultatif)
CONF_HC_START = "offpeak_start"
CONF_HC_END = "offpeak_end"
CONF_DEADLINE = "deadline"
CONF_TARGET_TEMP = "target_temperature"
CONF_HYSTERESIS = "hysteresis"
CONF_SAFETY_TEMP = "safety_temperature"
CONF_MAX_MANUAL_MIN = "max_manual_minutes"
CONF_ALLOW_EXTERNAL = "allow_external_control"
CONF_FORCE_API = "force_api"  # "auto" | "json" | "text" (secours si la détection échoue)

DEFAULT_SCAN_INTERVAL = 5
DEFAULT_TARGET_TEMP = 55.0
DEFAULT_HYSTERESIS = 3.0
DEFAULT_SAFETY_TEMP = 65.0
DEFAULT_MAX_MANUAL_MIN = 720
DEFAULT_HC_START = "23:00:00"
DEFAULT_HC_END = "06:00:00"
DEFAULT_DEADLINE = "06:00:00"
DEFAULT_HOT_ENERGY = 3.0
DEFAULT_DECLARED_POWER = 2000

TEMP_SOURCES = ["none", "router", "entity"]
POWER_SOURCES = ["declared", "meter", "calibration"]
HOT_METHODS = ["temperature", "thermostat", "energy"]

# --- modes de fonctionnement
MODE_OFF = "off"
MODE_SOLAR = "solar"
MODE_GUARANTEE = "solar_guarantee"
MODE_FORCED = "forced"
MODE_EXTERNAL = "external"
USER_MODES = [MODE_OFF, MODE_SOLAR, MODE_GUARANTEE, MODE_FORCED]
ALL_MODES = USER_MODES + [MODE_EXTERNAL]

# --- pilotage externe
EXTERNAL_TIMEOUT_S = 30 * 60
EXTERNAL_KEYS = ["mode", "boost", "target_temperature"]
FORCE_CHUNK_MIN = 30  # durée de chaque forçage envoyé au routeur
FORCE_RENEW_BELOW_MIN = 10  # renouvelé quand il reste moins de 10 min

# --- détection du thermostat (sans sonde)
THERMO_OPEN_MIN = 90  # ouverture minimale (%) pour juger
THERMO_JUMP_RATIO = 0.6  # saut d'injection ≥ 60 % de la puissance du ballon
THERMO_METER_RATIO = 0.1  # compteur dédié : < 10 % de la puissance = coupé
THERMO_HOLD_S = 120

EVENT_TARGET_MISSED = f"{DOMAIN}_target_missed"
EVENT_EXTERNAL_EXPIRED = f"{DOMAIN}_external_control_expired"
EVENT_THERMOSTAT = f"{DOMAIN}_thermostat_open"

STORAGE_VERSION = 1
