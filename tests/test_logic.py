"""Tests de la logique de pilotage avec un faux routeur (stubs Home Assistant).

Lancer : python3 tests/test_logic.py
"""
import asyncio
import datetime as dt
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "stubs"))
sys.path.insert(0, str(HERE.parent / "custom_components"))

from homeassistant.config_entries import ConfigEntry  # noqa: E402
from homeassistant.core import HomeAssistant, _State  # noqa: E402
from homeassistant.exceptions import ServiceValidationError  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402

import types  # noqa: E402

_pkg = types.ModuleType("f1atb_routeur")
_pkg.__path__ = [str(HERE.parent / "custom_components" / "f1atb_routeur")]
sys.modules["f1atb_routeur"] = _pkg  # sans exécuter __init__.py (qui dépend de tout HA)

from f1atb_routeur import api as A  # noqa: E402
from f1atb_routeur import parsers as P  # noqa: E402
from f1atb_routeur.coordinator import F1atbCoordinator  # noqa: E402
import test_parsers as T  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=1))


class FakeClient:
    def __init__(self, cfg, fw):
        self.base_url = "http://x"
        self.firmware = fw
        self._cfg = cfg
        self.live = {"temperatures": [44.1, None, None, None], "grid_net_w": 0.0, "tariff": None,
                     "actions": {0: {"index": 0, "name": "Chauffe-eau", "opening": 0, "force_min": 0}}}
        self.commands = []

    async def async_detect(self):
        return self.firmware

    async def async_get_config(self):
        return self._cfg

    async def async_get_live(self):
        return {**self.live, "actions": {k: dict(v) for k, v in self.live["actions"].items()}}

    async def async_get_system(self):
        return {"mac": "aa:bb", "ip": "192.168.1.201"}

    async def async_force(self, idx, minutes, current):
        self.commands.append(minutes)
        self.live["actions"][idx]["force_min"] = minutes


def at(h, m):
    dt_util.NOW[0] = dt.datetime(2026, 11, 24, h, m, tzinfo=TZ)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok -", msg)


async def cycle(c):
    c.data = await c._async_update_data()
    return c.data


async def main():
    cfg17 = A.RouterConfig(
        firmware=P.FirmwareInfo(P.FW_JSON, "17.30"), name="ECS_F1ATB", source="ShellyPro",
        actions=P.actions_from_parafixe(T.PARAFIXE_17), temp_names=["T°_ECS", "", "", ""], known_ips=[],
    )
    hass = HomeAssistant()
    entry = ConfigEntry({"host": "192.168.1.201", "water_heater_action": 0, "temp_source": "router",
                         "temp_channel": 0, "power_source": "declared", "declared_power": 2153,
                         "hot_method": "temperature"},
                        {"offpeak_start": "23:00:00", "offpeak_end": "06:00:00", "deadline": "06:00:00", "target_temperature": 55})
    client = FakeClient(cfg17, cfg17.firmware)
    c = F1atbCoordinator(hass, entry, client)
    await c.async_load()

    at(20, 0)
    d = await cycle(c)
    check(c.user_mode == "solar", "plage ON dans le planning → mode par défaut « Solaire seul »")
    check(d["slot"]["kind"] == "off" and d["desired"] is None and client.commands == [], "20:00, Solaire seul : aucun forçage")

    await c.async_set_mode("solar_guarantee")
    at(23, 30)
    d = await cycle(c)
    check(client.commands == [30] and d["reason"] == "boost", "23:30, 44 °C < 52 °C : rattrapage, forçage 30 min")
    client.live["actions"][0]["opening"] = 100
    client.live["actions"][0]["force_min"] = 25
    d = await cycle(c)
    check(client.commands == [30] and d["routed_power_w"] == 2153, "forçage en cours non renouvelé ; puissance estimée 2153 W")
    client.live["actions"][0]["force_min"] = 8
    await cycle(c)
    check(client.commands == [30, 30], "renouvelé quand il reste moins de 10 min")
    client.live["temperatures"][0] = 55.2
    d = await cycle(c)
    check(client.commands[-1] == 0 and d["reached"], "consigne atteinte : fin du forçage (retour au planning)")
    client.live["temperatures"][0] = 53.0
    await cycle(c)
    check(client.commands[-1] == 0 and len(client.commands) == 3, "hystérésis : pas de reprise à 53 °C")

    at(9, 0)
    client.live["temperatures"][0] = 40.0
    await cycle(c)
    check(len(client.commands) == 3, "9:00 hors heures creuses : pas de rattrapage")

    # Entité heures creuses active tout le week-end : pas de rattrapage en journée
    entry.options["offpeak_entity"] = "binary_sensor.hc"
    hass.states["binary_sensor.hc"] = _State("on")
    at(14, 0)
    await cycle(c)
    check(len(client.commands) == 3, "HC actives à 14:00 (week-end) : pas de rattrapage avant l'heure de début")
    at(23, 10)
    await cycle(c)
    check(client.commands[-1] == 30, "HC actives à 23:10 : rattrapage")
    client.live["temperatures"][0] = 70.0
    d = await cycle(c)
    check(d["desired"] is None and client.commands[-1] == 0, "sécurité thermique : plus de forçage à 70 °C")
    client.live["temperatures"][0] = 40.0
    del entry.options["offpeak_entity"]

    # Pilotage externe
    at(12, 0)
    client.live["actions"][0]["force_min"] = 0
    await c.async_set_external_control(True, "Chef d'orchestre énergie", ["mode"])
    await c.async_set_mode("off", controller="Chef d'orchestre énergie")
    d = await cycle(c)
    check(c.effective_mode == "external" and client.commands[-1] == -30, "pilote externe : arrêt forcé 30 min")
    try:
        await c.async_set_mode("solar")
        check(False, "refus attendu")
    except ServiceValidationError as err:
        check(err.translation_key == "externally_controlled", "l'utilisateur sans override est refusé")
    at(12, 31)
    client.live["actions"][0]["force_min"] = -1
    d = await cycle(c)
    check(c.effective_mode != "external" and any(e[0].endswith("external_control_expired") for e in hass.bus.events),
          "sans renouvellement pendant 30 min : le pilotage expire")
    check(client.commands[-1] == 0, "après expiration : fin de l'arrêt forcé")

    await c.async_set_external_control(True, "Chef", ["mode"])
    await c.async_set_mode("off", controller="Chef")
    await c.async_set_mode("solar", override=True)
    check(c.external is None and c.user_mode == "solar", "override de l'utilisateur : fin du pilotage externe")

    # État lisible
    d = await cycle(c)
    check(d["status"] in ("waiting_surplus", "idle", "solar", "hot") and "power_w" in d["status_info"], "capteur d'état renseigné")

    # Affichage seulement (control_enabled à l'arrêt)
    client.live["actions"][0]["force_min"] = 0
    await c.async_set_mode("forced", duration_min=30)
    await cycle(c)
    n = len(client.commands)
    await c.async_set_control_enabled(False)
    d = await cycle(c)
    check(client.commands[-1] == 0 and len(client.commands) == n + 1, "affichage seulement : notre marche forcée est levée une fois")
    await cycle(c)
    check(len(client.commands) == n + 1 and d["status_info"]["display_only"], "affichage seulement : plus aucune commande")
    for fn in (lambda: c.async_set_mode("off"), lambda: c.async_boost(), lambda: c.async_set_external_control(True, "Chef", ["mode"])):
        try:
            await fn()
            check(False, "refus attendu")
        except ServiceValidationError as err:
            assert err.translation_key == "control_disabled"
    check(True, "affichage seulement : mode, rattrapage et prise de main refusés")
    await c.async_set_control_enabled(True)
    await c.async_set_mode("solar")

    # Raison transmise par le pilote
    await c.async_set_external_control(True, "Chef", ["mode"], reason="Batteries prioritaires")
    await c.async_set_mode("off", controller="Chef")
    d = await cycle(c)
    check(d["status"] == "blocked" and d["status_info"]["reason"] == "Batteries prioritaires" and d["status_info"]["controller"] == "Chef",
          "pilote : état « bloqué » avec la raison")
    await c.async_set_external_control(False, "Chef", None)

    # Mode arrêt et marche forcée manuelle
    client.live["actions"][0]["force_min"] = 0
    await c.async_set_mode("off")
    await cycle(c)
    check(client.commands[-1] == -30, "mode Arrêt : arrêt forcé")
    await c.async_set_mode("forced", duration_min=60)
    await cycle(c)
    check(client.commands[-1] == 30, "marche forcée manuelle : forçage ON")
    at(13, 32)
    client.live["actions"][0]["force_min"] = 0
    await cycle(c)
    check(c.user_mode == "off", "fin de la marche forcée : retour au mode précédent")

    # Thermostat (sans sonde) : saut de consommation au compteur
    entry2 = ConfigEntry({"host": "h", "water_heater_action": 0, "temp_source": "none", "power_source": "declared",
                          "declared_power": 2000, "hot_method": "thermostat"}, {}, entry_id="e2")
    c2 = F1atbCoordinator(hass, entry2, FakeClient(cfg17, cfg17.firmware))
    await c2.async_load()
    c2.client.live["actions"][0]["opening"] = 100
    for net in (500, 500, -1500):
        c2.client.live["grid_net_w"] = net
        d = await cycle(c2)
    check(d["thermostat_open"] and d["reached"] and d["routed_power_w"] == 0, "thermostat : saut de -2000 W à ouverture 100 % → coupé, ballon chaud")
    c3 = F1atbCoordinator(hass, ConfigEntry(dict(entry2.data), {}, entry_id="e3"), FakeClient(cfg17, cfg17.firmware))
    await c3.async_load()
    for opening, net in ((0, 300), (100, 320), (100, 310)):
        c3.client.live["actions"][0]["opening"] = opening
        c3.client.live["grid_net_w"] = net
        d = await cycle(c3)
    check(d["thermostat_open"], "thermostat : mise en marche sans hausse de consommation → déjà coupé")
    c4 = F1atbCoordinator(hass, ConfigEntry(dict(entry2.data), {}, entry_id="e4"), FakeClient(cfg17, cfg17.firmware))
    await c4.async_load()
    for opening, net in ((0, 300), (100, 2300), (100, 2290)):
        c4.client.live["actions"][0]["opening"] = opening
        c4.client.live["grid_net_w"] = net
        d = await cycle(c4)
    check(not d["thermostat_open"] and d["routed_power_w"] == 2000, "thermostat : mise en marche avec +2000 W → fermé, chauffe")

    # 16.xx : séquences de commandes réelles
    sent = []

    class C16(A.F1atbClient):
        async def _get(self, path, **kw):
            sent.append(path)
            return ""

    cl = C16(None, "192.168.1.131")
    cl.firmware = P.FirmwareInfo(P.FW_TEXT, "16.10")
    await cl.async_force(1, 30, 0)
    await cl.async_force(1, -30, 30)
    await cl.async_force(1, 0, 25)
    await cl.async_force(1, 0, -20)
    await cl.async_force(1, 30, -20)
    b = "/ajax_etatActions?NumAction=1&Force="
    check(sent == [b + "1", b + "-1", b + "-1", b + "-1", b + "1", b + "1", b + "1"],
          "16.xx : ON ; ON→arrêt = deux Off ; fin de marche = Off ; fin d'arrêt = ON ; arrêt→marche = deux ON")
    sent.clear()
    cl.firmware = P.FirmwareInfo(P.FW_JSON, "17.30")
    await cl.async_force(0, -30, 0)
    check(sent == ["/ForceAction?NumAction=0&Force=-30"], "17.xx : /ForceAction avec la durée")
    # « Ouverture si forcée » (17.xx) : relecture, un seul champ modifié, vérification
    import copy
    import json as _json
    router = copy.deepcopy(T.PARAFIXE_17)
    posts = []

    class CW(A.F1atbClient):
        async def _get(self, path, **kw):
            return _json.dumps(router) if path == "/ParaFixe" else ""

        async def _post(self, path, body, content_type):
            posts.append((path, content_type))
            router.clear()
            router.update(_json.loads(body))

    cw = CW(None, "192.168.1.201")
    cw.firmware = P.FirmwareInfo(P.FW_JSON, "17.30")
    orig = A.asyncio.sleep
    A.asyncio.sleep = lambda s: orig(0)
    await cw.async_set_force_opening(0, 80)
    A.asyncio.sleep = orig
    check(router["Actions"][0]["ForceOuvre"] == 80 and router["password"] == "x" and router["Actions"][0]["Periodes"][3]["Vmin"] == -20,
          "ouverture si forcée = 80 % ; reste de la configuration renvoyé inchangé")
    check(posts == [("/ParaNew", "application/json")], "une seule écriture /ParaNew en JSON")
    cw.firmware = P.FirmwareInfo(P.FW_TEXT, "16.10")
    try:
        await cw.async_set_force_opening(0, 50)
        check(False, "refus attendu en 16.xx")
    except A.F1atbError:
        check(True, "16.xx : réglage refusé (n'existe pas)")
    print("\nTous les tests de logique passent.")


asyncio.run(main())
