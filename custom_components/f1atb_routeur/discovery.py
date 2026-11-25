"""Recherche des routeurs F1ATB sur le réseau local.

Pour les routeurs dont l'adresse IP fixe est réglée dans le routeur (sans DHCP), que la
découverte DHCP de Home Assistant ne voit pas. Chaque adresse du réseau local reçoit une
seule lecture de la page d'accueil (« / ») ; un routeur F1ATB s'y reconnaît à la mention
« F1ATB ». Aucune autre adresse n'est appelée.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging

from aiohttp import ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PROBE_TIMEOUT = ClientTimeout(total=1.5)
CONCURRENCY = 32
MAX_HOSTS = 1024


async def async_local_hosts(hass: HomeAssistant) -> list[str]:
    """Adresses à interroger : réseaux IPv4 actifs de Home Assistant, ramenés à /24 au plus."""
    from homeassistant.components import network

    hosts: list[str] = []
    seen: set[str] = set()
    try:
        adapters = await network.async_get_adapters(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Adaptateurs réseau illisibles : %s", err)
        return hosts
    for adapter in adapters:
        if not adapter.get("enabled"):
            continue
        for ip in adapter.get("ipv4") or []:
            addr = ip.get("address")
            prefix = int(ip.get("network_prefix") or 24)
            if not addr or addr.startswith(("127.", "169.254.")):
                continue
            net = ipaddress.ip_interface(f"{addr}/{max(prefix, 24)}").network
            for host in net.hosts():
                h = str(host)
                if h != addr and h not in seen:
                    seen.add(h)
                    hosts.append(h)
    return hosts[:MAX_HOSTS]


async def async_scan(hass: HomeAssistant, exclude: set[str]) -> list[str]:
    """Adresses du réseau local qui répondent comme un routeur F1ATB."""
    session = async_get_clientsession(hass)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def probe(host: str) -> str | None:
        async with sem:
            try:
                async with session.get(f"http://{host}/", timeout=PROBE_TIMEOUT, allow_redirects=False) as resp:
                    if resp.status != 200:
                        return None
                    body = await resp.content.read(16384)
                    return host if b"F1ATB" in body else None
            except Exception:  # noqa: BLE001 - adresse muette ou autre appareil
                return None

    hosts = [h for h in await async_local_hosts(hass) if h not in exclude]
    results = await asyncio.gather(*(probe(h) for h in hosts))
    found = [h for h in results if h]
    _LOGGER.debug("Recherche F1ATB : %d adresses, trouvés %s", len(hosts), found)
    return found
