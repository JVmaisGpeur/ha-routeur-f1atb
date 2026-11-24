"""Intégration Home Assistant « Routeur F1ATB » (ha-routeur-f1atb)."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import F1atbClient
from .const import CARD_FILENAME, CARD_URL, CONF_HOST, DOMAIN
from .coordinator import F1atbCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type F1atbConfigEntry = ConfigEntry[F1atbCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async_setup_services(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Sert la carte Lovelace et la charge automatiquement dans le tableau de bord."""
    key = f"{DOMAIN}_card_registered"
    if hass.data.get(key):
        return
    path = Path(__file__).parent / CARD_FILENAME
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), True)])
        add_extra_js_url(hass, f"{CARD_URL}?v=1.0.0")
        hass.data[key] = True
    except Exception as err:  # noqa: BLE001 - la carte est facultative
        _LOGGER.warning("Carte non chargée automatiquement (%s) : ajoutez %s en ressource", err, CARD_URL)


async def async_setup_entry(hass: HomeAssistant, entry: F1atbConfigEntry) -> bool:
    await _async_register_card(hass)
    client = F1atbClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = F1atbCoordinator(hass, entry, client)
    await coordinator.async_load()
    # Routeur éteint : ce n'est pas une erreur. L'intégration se charge quand même,
    # « Connecté » passe à off et tout revient quand le routeur répond.
    await coordinator.async_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_propose_known_routers(hass, entry, coordinator)
    return True


def _async_propose_known_routers(hass: HomeAssistant, entry: ConfigEntry, coordinator: F1atbCoordinator) -> None:
    """Propose (sans les ajouter) les autres routeurs que ce routeur connaît."""
    if not coordinator.config:
        return
    configured = {e.data.get(CONF_HOST) for e in hass.config_entries.async_entries(DOMAIN)}
    own = entry.data.get(CONF_HOST)
    for ip in coordinator.config.known_ips:
        if ip in configured or ip == own or ip == (coordinator.system or {}).get("ip"):
            continue
        discovery_flow.async_create_flow(
            hass, DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data={CONF_HOST: ip}
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: F1atbConfigEntry) -> bool:
    coordinator: F1atbCoordinator = entry.runtime_data
    await coordinator.async_save()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
