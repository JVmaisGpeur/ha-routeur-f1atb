"""Client HTTP local du routeur F1ATB (firmware officiel, sans modification).

Règles :
- une seule requête à la fois vers le routeur (verrou) ;
- lecture seule, sauf les commandes de forçage temporaires (/ForceAction en 17.xx,
  /ajax_etatActions?Force= en 16.xx) ;
- une seule écriture permanente, faite uniquement quand l'utilisateur change lui-même
  « Ouverture si forcée » (17.xx, /ParaNew) : jamais par le pilotage automatique ;
- aucune adresse découverte automatiquement n'est jamais appelée.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

from aiohttp import ClientError, ClientSession, ClientTimeout

from . import parsers as P

_LOGGER = logging.getLogger(__name__)

TIMEOUT = ClientTimeout(total=5)
RETRIES = 3
V16_FORCE_STEP_MIN = 30  # en 16.xx, chaque Force=1 ajoute 30 min (constaté en 16.10)


class F1atbError(Exception):
    """Routeur injoignable ou réponse inattendue."""


@dataclass
class RouterConfig:
    """Configuration lue dans le routeur (sans aucun secret)."""

    firmware: P.FirmwareInfo
    name: str
    source: str | None
    actions: list[P.ActionConfig] = field(default_factory=list)
    temp_names: list[str] = field(default_factory=list)
    known_ips: list[str] = field(default_factory=list)
    raw_redacted: dict = field(default_factory=dict)


class F1atbClient:
    def __init__(self, session: ClientSession, host: str) -> None:
        host = host.strip().rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = "http://" + host
        self.base_url = host
        self._session = session
        self._lock = asyncio.Lock()
        self.firmware: P.FirmwareInfo | None = None

    async def _get(self, path: str, *, retries: int = RETRIES, allow_404: bool = False) -> str | None:
        url = self.base_url + path
        last: Exception | None = None
        for attempt in range(retries):
            try:
                async with self._lock:
                    async with self._session.get(url, timeout=TIMEOUT) as resp:
                        if resp.status == 404 and allow_404:
                            return None
                        resp.raise_for_status()
                        raw = await resp.read()
                        return raw.decode("utf-8", errors="replace")
            except (ClientError, asyncio.TimeoutError) as err:
                last = err
                if attempt + 1 < retries:
                    await asyncio.sleep(0.5)
        raise F1atbError(f"{path}: {last}")

    async def _post(self, path: str, body: str, content_type: str) -> None:
        url = self.base_url + path
        try:
            async with self._lock:
                async with self._session.post(
                    url, data=body.encode("utf-8"), headers={"Content-Type": content_type}, timeout=TIMEOUT
                ) as resp:
                    resp.raise_for_status()
                    await resp.read()
        except (ClientError, asyncio.TimeoutError) as err:
            raise F1atbError(f"{path}: {err}") from err

    # ------------------------------------------------------------ détection
    async def async_detect(self) -> P.FirmwareInfo:
        """17.xx si /ParaFixe répond en JSON, sinon 16.xx via /ParaRouteurAjax."""
        txt = await self._get("/ParaFixe", allow_404=True, retries=2)
        cfg = P.parse_json(txt) if txt else None
        if cfg is not None:
            fw = P.FirmwareInfo(P.FW_JSON, P.version_from_parafixe(cfg) or "?", cfg.get("nomRouteur"))
        else:
            txt = await self._get("/ParaRouteurAjax", allow_404=True, retries=2)
            if not txt:
                raise F1atbError("ni /ParaFixe ni /ParaRouteurAjax : routeur F1ATB non reconnu")
            info = P.parse_para_routeur_ajax(txt)
            fw = P.FirmwareInfo(P.FW_TEXT, info.get("version") or "?", info.get("name"))
        self.firmware = fw
        return fw

    async def async_get_config(self) -> RouterConfig:
        fw = self.firmware or await self.async_detect()
        if fw.api == P.FW_JSON:
            cfg = P.parse_json(await self._get("/ParaFixe") or "") or {}
            temp_names = [str(cfg.get(f"nomTemperature{c}") or "").strip() for c in range(4)]
            return RouterConfig(
                firmware=fw,
                name=str(cfg.get("nomRouteur") or cfg.get("hostname") or "F1ATB").strip(),
                source=cfg.get("Source"),
                actions=P.actions_from_parafixe(cfg),
                temp_names=temp_names,
                known_ips=P.known_ips_from_parafixe(cfg),
                raw_redacted=P.redact(cfg),
            )
        para = P.parse_para_routeur_ajax(await self._get("/ParaRouteurAjax") or "")
        actions, temp_names = P.parse_actions_ajax(await self._get("/ActionsAjax") or "")
        return RouterConfig(
            firmware=fw,
            name=para.get("name") or "F1ATB",
            source=para.get("source"),
            actions=actions,
            temp_names=temp_names,
            known_ips=para.get("known_ips") or [],
            raw_redacted={k: v for k, v in para.items() if k != "raw_fields"},
        )

    # ------------------------------------------------------------ mesures
    async def async_get_live(self) -> dict:
        data = P.parse_ajax_data(await self._get("/ajax_data") or "")
        data["actions"] = P.parse_etat_actions(await self._get("/ajax_etatActions") or "")
        return data

    async def async_get_system(self) -> dict:
        return P.parse_data_esp32(await self._get("/ajax_dataESP32") or "")

    # ------------------------------------------------------------ forçages
    async def async_force(self, index: int, minutes: int, current_force_min: int) -> None:
        """Forçage temporaire décompté par le routeur.

        minutes > 0 : marche forcée ; < 0 : arrêt forcé ; 0 : fin du forçage.
        `current_force_min` : forçage en cours lu dans /ajax_etatActions.
        """
        fw = self.firmware or await self.async_detect()
        if fw.api == P.FW_JSON:
            await self._get(f"/ForceAction?NumAction={int(index)}&Force={int(minutes)}", retries=1)
            return
        # 16.xx : Force=1 ajoute 30 min de marche ; Force=-1 annule une marche forcée,
        # sinon lance 30 min d'arrêt forcé (constaté sur un 16.10).
        base = f"/ajax_etatActions?NumAction={int(index)}&Force="
        if minutes > 0:
            if current_force_min < 0:
                _LOGGER.debug("16.xx : arrêt forcé en cours, marche forcée reportée")
                return
            await self._get(base + "1", retries=1)
        elif minutes < 0:
            if current_force_min > 0:
                await self._get(base + "-1", retries=1)  # annule la marche forcée
                await self._get(base + "-1", retries=1)  # puis arrêt forcé 30 min
            elif current_force_min == 0:
                await self._get(base + "-1", retries=1)
            # arrêt déjà en cours : il expirera, puis sera relancé
        else:
            if current_force_min > 0:
                await self._get(base + "-1", retries=1)
            # 16.xx : un arrêt forcé expire seul (≤ 30 min) ; aucune commande d'annulation vérifiée

    # ------------------------------------------------------------ réglage utilisateur
    async def async_set_force_opening(self, index: int, value: int) -> None:
        """« Ouverture si forcée » d'une action (17.xx uniquement), enregistrée dans le routeur.

        Relit toute la configuration, change ce seul champ, la renvoie telle quelle
        (secrets compris, jamais journalisés) puis vérifie par une relecture. Le format
        de la page Actions (JSON) est essayé d'abord, puis text/plain (anciennes 17.xx).
        """
        fw = self.firmware or await self.async_detect()
        if fw.api != P.FW_JSON:
            raise F1atbError("réglage disponible seulement en 17.xx")
        value = max(0, min(100, int(value)))
        for content_type in ("application/json", "text/plain"):
            cfg = P.parse_json(await self._get("/ParaFixe") or "")
            actions = (cfg or {}).get("Actions") or []
            if not 0 <= index < len(actions):
                raise F1atbError("action introuvable dans /ParaFixe")
            if P.to_int(actions[index].get("ForceOuvre")) == value:
                return
            actions[index]["ForceOuvre"] = value
            await self._post("/ParaNew", json.dumps(cfg, ensure_ascii=False, separators=(",", ":")), content_type)
            await asyncio.sleep(1)
            check = P.parse_json(await self._get("/ParaFixe") or "") or {}
            got = ((check.get("Actions") or [{}] * (index + 1))[index] or {}).get("ForceOuvre")
            if P.to_int(got) == value:
                return
        raise F1atbError("le routeur n'a pas pris en compte le réglage")
