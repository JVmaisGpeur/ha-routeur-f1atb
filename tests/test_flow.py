"""Parcours de l'installation (stubs) : une question à la fois, champs utiles seulement.

Lancer : python3 tests/test_flow.py
"""
import asyncio
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "stubs"))
_pkg = types.ModuleType("f1atb_routeur")
_pkg.__path__ = [str(HERE.parent / "custom_components" / "f1atb_routeur")]
sys.modules["f1atb_routeur"] = _pkg

from f1atb_routeur import api as A  # noqa: E402
from f1atb_routeur import config_flow as CF  # noqa: E402
from f1atb_routeur import parsers as P  # noqa: E402
from homeassistant.helpers import discovery_flow  # noqa: E402
import test_parsers as T  # noqa: E402

CFG17 = A.RouterConfig(P.FirmwareInfo(P.FW_JSON, "17.30"), "ECS_F1ATB", "ShellyPro",
                       P.actions_from_parafixe(T.PARAFIXE_17), ["T°_ECS", "", "", ""], [])
acts16, names16 = P.parse_actions_ajax(T.ACTIONS_AJAX_16)
CFG16 = A.RouterConfig(P.FirmwareInfo(P.FW_TEXT, "16.10"), "Routeur_ECS_Exemple", "ShellyPro", acts16, names16, [])


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok -", msg)


def keys(res):
    return [k.schema for k in res["schema"].schema] if res.get("schema") else []


async def main():
    probes = {"192.168.1.201": (CFG17, {"mac": "aa:bb"}, [44.1, None, None, None]),
              "192.168.1.131": (CFG16, {"mac": "cc:dd"}, [None, None, None, None])}

    async def fake_probe(hass, host):
        if host not in probes:
            raise A.F1atbError("x")
        return probes[host]

    from f1atb_routeur.discovery import ScanResult

    scan_found = list(probes)

    async def fake_scan(hass):
        return ScanResult(found=list(scan_found), networks=["192.168.1.0/24"], tested=253, web=len(scan_found) + 3)

    CF._probe = fake_probe
    CF.async_scan = fake_scan

    # --- Ton routeur 17.30 : recherche réseau, sonde T°_ECS, puissance déclarée
    f = CF.F1atbConfigFlow()
    f.hass = None
    r = await f.async_step_user()
    check(r["type"] == "menu" and r["menu_options"] == ["search", "manual"], "1er écran : Rechercher / Saisir l'adresse")
    r = await f.async_step_search()
    check(r["step_id"] == "search" and keys(r) == ["routers"], "recherche : liste des routeurs trouvés à cocher")
    r = await f.async_step_search({"routers": ["192.168.1.201", "192.168.1.131"]})
    check(len(discovery_flow.CREATED) == 1 and discovery_flow.CREATED[0][1]["host"] == "192.168.1.131",
          "2e routeur coché : proposé à part dans « Découverts »")
    check(r["step_id"] == "temperature", "une seule sortie active : question de la sortie sautée")
    check(keys(r) == ["temp_source"], "écran température : une seule question")
    r = await f.async_step_temperature({"temp_source": "router"})
    check(r["step_id"] == "power" and keys(r) == ["power_source"], "une seule sonde (T°_ECS) : choisie d'office, méthode « température »")
    r = await f.async_step_power({"power_source": "declared"})
    check(r["step_id"] == "power_declared" and keys(r) == ["declared_power"], "puissance déclarée : seulement la valeur en W")
    r = await f.async_step_power_declared({"declared_power": 2153})
    check(r["step_id"] == "offpeak" and keys(r) == ["target_temperature", "offpeak_start", "offpeak_end"], "dernier écran : consigne + heures creuses")
    r = await f.async_step_offpeak({"target_temperature": 55, "offpeak_start": "23:00:00", "offpeak_end": "06:00:00"})
    d = r["data"]
    check(r["type"] == "create_entry" and d["temp_source"] == "router" and d["temp_channel"] == 0 and d["hot_method"] == "temperature"
          and d["water_heater_action"] == 0 and "temp_entity" not in d and "meter_entity" not in d, "entrée créée sans champ inutile")
    check(r["options"]["deadline"] == "06:00:00", "heure limite = fin des heures creuses")

    # --- Routeur 16.10 d exemple : pas de sonde, compteur dédié
    f = CF.F1atbConfigFlow()
    f.hass = None
    r = await f.async_step_manual({"host": "192.168.1.131"})
    check(r["step_id"] == "temperature", "16.10 : relais seul actif, sortie choisie d'office")
    check(r["schema"].schema and list(r["schema"].schema)[0].default == "none", "pas de sonde : « Pas de sonde » proposé par défaut")
    r = await f.async_step_temperature({"temp_source": "none"})
    check(r["step_id"] == "hot" and keys(r) == ["hot_method"], "sans sonde : comment savoir que l'eau est chaude ?")
    r = await f.async_step_hot({"hot_method": "thermostat"})
    r = await f.async_step_power({"power_source": "meter"})
    check(r["step_id"] == "power_meter" and keys(r) == ["meter_entity"], "compteur dédié : seulement le capteur")
    r = await f.async_step_power_meter({"meter_entity": "sensor.ecs_power"})
    check(keys(r) == ["offpeak_start", "offpeak_end"], "sans sonde : pas de consigne demandée")
    r = await f.async_step_offpeak({"offpeak_start": "22:00:00", "offpeak_end": "06:00:00"})
    d = r["data"]
    check(d["hot_method"] == "thermostat" and d["water_heater_action"] == 1 and "temp_channel" not in d and "target_temperature" not in r["options"],
          "entrée 16.10 : relais 1, thermostat, sans consigne")

    # --- Recherche sans nouveau routeur : compte rendu affiché sur l'écran de saisie
    scan_found[:] = ["192.168.1.201"]
    f = CF.F1atbConfigFlow()
    f.hass = None
    f._async_current_entries = lambda include_ignore=False: [types.SimpleNamespace(data={"host": "192.168.1.201"})]
    r = await f.async_step_search()
    check(r["step_id"] == "manual" and r["errors"] == {"base": "none_found"}, "aucun nouveau routeur : saisie de l'adresse")
    scan = r["placeholders"]["scan"]
    check("192.168.1.0/24" in scan and "253 adresses" in scan and "Déjà ajouté(s) : 192.168.1.201" in scan,
          "compte rendu : réseau, adresses testées, routeur déjà ajouté")
    r = await f.async_step_manual()
    check(r["placeholders"] == {"scan": ""}, "saisie directe : pas de compte rendu")

    # --- Adresse inconnue
    f = CF.F1atbConfigFlow()
    f.hass = None
    r = await f.async_step_manual({"host": "10.0.0.9"})
    check(r["errors"] == {"base": "cannot_connect"}, "adresse sans routeur : message d'erreur")
    print("\nParcours d'installation : tous les tests passent.")


asyncio.run(main())
