"""Recherche des routeurs F1ATB sur le réseau local.

Pour les routeurs dont l'adresse IP fixe est réglée dans le routeur (sans DHCP), que la
découverte DHCP de Home Assistant ne voit pas. Deux temps :

1. on regarde quelles adresses du réseau local acceptent une connexion sur le port 80
   (simple ouverture de connexion, rien n'est envoyé) ;
2. ces serveurs web reçoivent une seule lecture de /ajax_dataESP32, page en lecture seule
   du routeur F1ATB (16.xx et 17.xx). Un routeur s'y reconnaît à son format (séparateurs
   et adresse MAC). Un autre appareil répond « page introuvable ».

Aucune autre adresse n'est appelée et aucune commande n'est envoyée.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import ipaddress
import logging

from aiohttp import ClientTimeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .parsers import looks_like_data_esp32

_LOGGER = logging.getLogger(__name__)

PORT = 80
CONNECT_TIMEOUT = 2.0  # un ESP32 en économie d'énergie Wi-Fi peut mettre du temps à répondre
CONNECT_CONCURRENCY = 64
READ_TIMEOUT = ClientTimeout(total=8)
READ_CONCURRENCY = 8
MAX_HOSTS = 1024
MAX_WEB = 128
PROBE_PATH = "/ajax_dataESP32"


@dataclass
class ScanResult:
    found: list[str] = field(default_factory=list)
    networks: list[str] = field(default_factory=list)
    tested: int = 0
    web: int = 0


async def async_local_hosts(hass: HomeAssistant) -> tuple[list[str], list[str]]:
    """Adresses à interroger : réseaux IPv4 actifs de Home Assistant, ramenés à /24 au plus."""
    from homeassistant.components import network

    hosts: list[str] = []
    nets: list[str] = []
    seen: set[str] = set()
    try:
        adapters = await network.async_get_adapters(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Recherche F1ATB : adaptateurs réseau illisibles (%s)", err)
        return hosts, nets
    for adapter in adapters:
        if not adapter.get("enabled"):
            continue
        for ip in adapter.get("ipv4") or []:
            addr = ip.get("address")
            prefix = int(ip.get("network_prefix") or 24)
            if not addr or addr.startswith(("127.", "169.254.")):
                continue
            net = ipaddress.ip_interface(f"{addr}/{max(prefix, 24)}").network
            if str(net) not in nets:
                nets.append(str(net))
            for host in net.hosts():
                h = str(host)
                if h != addr and h not in seen:
                    seen.add(h)
                    hosts.append(h)
    return hosts[:MAX_HOSTS], nets


async def _port_open(host: str, sem: asyncio.Semaphore) -> bool:
    async with sem:
        try:
            _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, PORT), CONNECT_TIMEOUT)
        except (OSError, asyncio.TimeoutError):
            return False
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()
        return True


async def async_scan(hass: HomeAssistant) -> ScanResult:
    """Adresses du réseau local qui répondent comme un routeur F1ATB."""
    hosts, nets = await async_local_hosts(hass)
    result = ScanResult(networks=nets, tested=len(hosts))
    conn_sem = asyncio.Semaphore(CONNECT_CONCURRENCY)
    opened = await asyncio.gather(*(_port_open(h, conn_sem) for h in hosts))
    web = [h for h, ok in zip(hosts, opened) if ok][:MAX_WEB]
    result.web = len(web)

    session = async_get_clientsession(hass)
    read_sem = asyncio.Semaphore(READ_CONCURRENCY)

    async def probe(host: str) -> str | None:
        async with read_sem:
            try:
                async with session.get(f"http://{host}{PROBE_PATH}", timeout=READ_TIMEOUT, allow_redirects=False) as resp:
                    if resp.status != 200:
                        return None
                    body = await resp.content.read(8192)
            except Exception:  # noqa: BLE001 - autre appareil, ou routeur trop lent
                return None
        return host if looks_like_data_esp32(body.decode("utf-8", errors="replace")) else None

    found = await asyncio.gather(*(probe(h) for h in web))
    result.found = [h for h in found if h]
    _LOGGER.info(
        "Recherche F1ATB sur %s : %d adresses, %d serveurs web, routeurs trouvés : %s",
        ", ".join(nets) or "aucun réseau", result.tested, result.web, result.found or "aucun",
    )
    return result
