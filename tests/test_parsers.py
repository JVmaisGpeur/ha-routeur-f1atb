"""Tests des décodeurs sur des réponses réelles (routeur 16.10 et 17.30, 24/11/2026).

Lancer : python3 tests/test_parsers.py   (aucune dépendance)
"""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "parsers", ROOT / "custom_components" / "f1atb_routeur" / "parsers.py"
)
P = importlib.util.module_from_spec(spec)
sys.modules["parsers"] = P
spec.loader.exec_module(P)

GS, RS, US, ES, FS = P.GS, P.RS, P.US, P.ES, P.FS

# ---- 16.10 (routeur de test, relais 1 en multi-sinus)
AJAX_DATA_16 = (
    "Deb" + RS + "24/11/2026 20:04:39" + RS + "ShellyPro" + RS + "TEMPO_BLANC" + RS + "8" + RS
    + "-127.00|-127.00|-127.00|-127.00|" + RS + "1" + GS
    + RS.join(["311", "0", "336", "0", "1915", "84", "232555", "6259"]) + GS
    + RS.join(["0", "0", "0", "0", "0", "0", "68304", "5115135"]) + GS + "Fin\r"
)
ETAT_16_FORCED_ON = (
    "-127.00|-127.00|-127.00|-127.00|" + GS + "ShellyPro" + GS + "3232235890" + GS + "1" + GS
    + "1" + RS + "Titre Relais 1" + RS + "0" + RS + "30" + RS + "0" + RS + GS
)
ESP32_16 = RS.join([
    "139.43", "1", "-65", "02:00:00:00:00:01", "2", "02:00:00:00:00:02", "Maison_IoT",
    "192.168.1.131" + US + "RMS-ESP32-0000001" + US + "2a01::1", "192.168.1.254", "255.255.255.0",
    "1, 6, 407", "1, 2, 12", "48", "93720", "36612", "Pas de Triac",
]) + GS
PARA_ROUTEUR_16 = GS.join([
    "ShellyPro", "ShellyPro", "192.168.1.131", "Routeur_ECS_Exemple", "16.10", "Production solaire",
    "Consommation réseau", "3232235890", "0", "1", "0", "1",
    "3232235907" + US + "Routeur_ECS_Exemple" + US + US + "1" + ES + "Titre Relais 1" + ES + "0" + ES + "7" + ES + "0" + FS + RS,
])
ACTIONS_AJAX_16 = (
    "-127.00|-127.00|-127.00|-127.00|" + RS + US + US + US + US + RS + "8" + RS + "0" + RS + "1" + RS + "500" + RS + "1" + GS
    + RS.join(["0", "Titre Triac", "", "50", "0|1", "", "0", "0", "0", "10", "0", "0", "1",
               "4", "2400", "0", "100", "1600", "1600", "0", "0", "-1", "255", "0", "0", "31"]) + RS + GS
    + RS.join(["2", "Titre Relais 1", "", "80", "17|1", "", "240", "0", "0", "5", "0", "0", "3",
               "1", "599", "0", "100", "1600", "1600", "0", "0", "-1", "255", "0", "0", "31",
               "3", "2209", "-25", "100", "1600", "1600", "0", "0", "-1", "255", "0", "0", "31",
               "2", "2400", "0", "100", "1600", "1600", "0", "200", "-1", "1", "0", "0", "28"]) + RS + GS
)

# ---- 17.30 (routeur ECS_F1ATB, extrait de /ParaFixe, secrets retirés)
PARAFIXE_17 = {
    "Routeur": "F1ATB", "VersionStocke": 1730, "nomRouteur": "ECS_F1ATB", "password": "x",
    "MQTTPwd": "y", "EnphaseUser": "z", "RMS_IP0": 3232235977, "RMSextIP": 3232235986,
    "Source": "ShellyPro",
    "Actions": [{
        "Action": 0, "Titre": "Chauffe-eau", "Actif": 1, "ForceOuvre": 100,
        "Periodes": [
            {"Hfin": 400, "Type": 1, "Vmin": 0, "Vmax": 100, "ONouvre": 100, "Tinf": 450, "Tsup": 480, "CanalTemp": 0, "Tarif": 31},
            {"Hfin": 598, "Type": 2, "Vmin": 0, "Vmax": 100, "ONouvre": 100, "Tinf": 500, "Tsup": 1580, "CanalTemp": 0, "Tarif": 31},
            {"Hfin": 950, "Type": 1, "Vmin": 0, "Vmax": 100, "ONouvre": 100, "Tinf": 1600, "Tsup": 1600, "CanalTemp": -1, "Tarif": 31},
            {"Hfin": 1850, "Type": 4, "Vmin": -20, "Vmax": 100, "ONouvre": 100, "Tinf": 600, "Tsup": 1580, "CanalTemp": 0, "Tarif": 31},
            {"Hfin": 2400, "Type": 1, "Vmin": 0, "Vmax": 10, "ONouvre": 100, "Tinf": 1600, "Tsup": 1600, "CanalTemp": -1, "Tarif": 31},
        ],
    }, {"Action": 1, "Titre": "Titre Relais 1", "Actif": 0, "ForceOuvre": 100, "Periodes": [
        {"Hfin": 2400, "Type": 3, "Vmin": 0, "Vmax": 100, "Tinf": 1600, "Tsup": 1600, "CanalTemp": -1, "Tarif": 31}]}],
}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok -", msg)


def main():
    d = P.parse_ajax_data(AJAX_DATA_16)
    check(d["grid_import_w"] == 311 and d["grid_export_w"] == 0 and d["grid_net_w"] == 311, "ajax_data 16 : soutirage/injection")
    check(d["tariff"] == "TEMPO_BLANC" and d["temperatures"] == [None] * 4, "ajax_data 16 : tarif et sondes absentes")

    e = P.parse_etat_actions(ETAT_16_FORCED_ON)
    check(e[1]["force_min"] == 30 and e[1]["opening"] == 0 and e[1]["name"] == "Titre Relais 1", "etatActions 16 : marche forcée 30 min")

    s = P.parse_data_esp32(ESP32_16)
    check(s["mac"] == "02:00:00:00:00:02", "dataESP32 : MAC de l'ESP32 (pas celle du point d'accès)")
    check(s["ip"] == "192.168.1.131" and s["hostname"] == "RMS-ESP32-0000001", "dataESP32 : IP et nom réseau")

    r = P.parse_para_routeur_ajax(PARA_ROUTEUR_16)
    check(r["version"] == "16.10" and r["name"] == "Routeur_ECS_Exemple", "ParaRouteurAjax : version et nom")
    check(r["known_ips"] == ["192.168.1.131"], "ParaRouteurAjax : routeurs connus sans l'adresse du Shelly")

    acts, tnames = P.parse_actions_ajax(ACTIONS_AJAX_16)
    check(len(acts) == 2 and acts[1].title == "Titre Relais 1" and acts[1].mode == "multi_sine", "ActionsAjax : 2 actions, relais en multi-sinus")
    sl = [x.as_dict() for x in acts[1].slots]
    check([x["kind"] for x in sl] == ["off", "route", "on"], "ActionsAjax : OFF / routage / ON")
    check(sl[0]["end"] == "5:59" and sl[1]["end"] == "22:05" and sl[1]["threshold_w"] == -25, "ActionsAjax : horaires et seuil -25 W")
    check(acts[0].mode == "inactive" and acts[0].is_triac, "ActionsAjax : triac inactif")

    fi = P.FirmwareInfo(P.FW_JSON, P.version_from_parafixe(PARAFIXE_17))
    check(fi.version == "17.30" and fi.tested, "ParaFixe : version 17.30")
    a17 = P.actions_from_parafixe(PARAFIXE_17)
    sl17 = [x.as_dict() for x in a17[0].slots]
    check([x["kind"] for x in sl17] == ["off", "on", "off", "route", "off"], "ParaFixe : planning 17.30")
    check(sl17[1]["t_below"] == 50.0 and sl17[1]["start"] == "4:00" and sl17[1]["end"] == "5:59", "ParaFixe : ON 4:00-5:59 si T ≤ 50 °C")
    check(sl17[3]["threshold_w"] == -20 and sl17[3]["t_below"] == 60.0 and sl17[3]["start"] == "9:30", "ParaFixe : routage -20 W, T ≤ 60 °C dès 9:30")
    check(P.known_ips_from_parafixe(PARAFIXE_17) == ["192.168.1.201"], "ParaFixe : routeurs connus (RMS_IP)")
    red = P.redact(PARAFIXE_17)
    check(red["password"] == "**REDACTED**" and red["MQTTPwd"] == "**REDACTED**" and red["EnphaseUser"] == "**REDACTED**", "secrets masqués")
    check(P.slot_at(a17[0].slots, 20 * 60).kind == "off" and P.slot_at(a17[0].slots, 12 * 60).kind == "route", "créneau en cours")
    print("\nTous les tests passent.")


if __name__ == "__main__":
    main()
