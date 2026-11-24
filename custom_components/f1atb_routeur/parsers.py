"""Décodage des réponses du routeur F1ATB (firmwares 16.xx et 17.xx).

Module sans dépendance à Home Assistant ni à aiohttp, pour pouvoir être testé seul.
Les firmwares répondent en texte avec des caractères de contrôle ASCII comme
séparateurs (16.xx et pages « ajax ») ou en JSON (/ParaFixe, /ParaVar en 17.xx).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

ES = chr(27)
FS = chr(28)
GS = chr(29)
RS = chr(30)
US = chr(31)

FW_JSON = "json"  # 17.xx : /ParaFixe en JSON
FW_TEXT = "text"  # 16.xx : /ParaRouteurAjax + /ActionsAjax en texte

# Types de plage du planning (champ « Type »)
SLOT_TYPES = {1: "off", 2: "on", 3: "route", 4: "route"}

# Champ « Actif » d'une action
ACTION_MODES = {
    0: "inactive",
    1: "cut",  # découpe sinus (triac) ou On/Off (relais)
    2: "multi_sine",
    3: "sine_train",
    4: "pwm",
    5: "half_sine",
}

# Clés de configuration à ne jamais conserver, journaliser ni afficher
SECRET_KEY_PATTERN = re.compile(r"pass|pwd|user|ssid|cle|token|key|topic", re.IGNORECASE)

PERIOD_FIELDS = (
    "Type", "Hfin", "Vmin", "Vmax", "Tinf", "Tsup", "Hmin", "Hmax",
    "CanalTemp", "SelAct", "Ooff", "O_on", "Tarif",
)
ACTION_HEAD_FIELDS = (
    "Actif", "Titre", "Host", "Port", "OrdreOn", "OrdreOff", "Repet", "Tempo",
    "Kp", "Ki", "Kd", "PID",
)


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    f = to_float(value)
    return None if f is None else int(f)


def _at(lst: list[str], i: int) -> str | None:
    return lst[i] if 0 <= i < len(lst) else None


def parse_temperatures(raw: str) -> list[float | None]:
    """« 44.1|-127.00|… » → [44.1, None, …] (-127 = sonde absente)."""
    temps: list[float | None] = []
    for part in raw.split("|")[:4]:
        val = to_float(part)
        temps.append(val if val is not None and val > -100 else None)
    while len(temps) < 4:
        temps.append(None)
    return temps


def centi_hours_to_minutes(hfin: Any) -> int:
    """Hfin en centièmes d'heure (950 = 9,5 h) → minutes depuis minuit."""
    val = to_float(hfin) or 0.0
    return max(0, min(1440, round(val * 60 / 100)))


def minutes_to_hhmm(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"


# ------------------------------------------------------------------ détection
@dataclass
class FirmwareInfo:
    """Version et format détectés."""

    api: str  # FW_JSON ou FW_TEXT
    version: str  # « 17.30 », « 16.10 »
    name: str | None = None

    @property
    def major(self) -> int | None:
        return to_int(self.version.split(".")[0]) if self.version else None

    @property
    def tested(self) -> bool:
        """Versions vérifiées sur un vrai routeur."""
        return self.major in (16, 17)


def version_from_parafixe(cfg: dict) -> str | None:
    raw = cfg.get("VersionStocke")
    val = to_int(raw)
    if val is None:
        return None
    if val >= 100:
        return f"{val // 100}.{val % 100:02d}"
    return str(val)


def parse_para_routeur_ajax(text: str) -> dict:
    """/ParaRouteurAjax (16.xx) : source, nom, version, adresses des autres routeurs."""
    parts = text.split(GS)
    out: dict[str, Any] = {"raw_fields": len(parts)}
    out["source"] = (_at(parts, 0) or "").strip() or None
    out["ip"] = (_at(parts, 2) or "").strip() or None
    out["name"] = (_at(parts, 3) or "").strip() or None
    version = None
    for p in parts:
        if re.fullmatch(r"\s*\d{1,2}\.\d{1,2}\s*", p):
            version = p.strip()
            break
    out["version"] = version
    out["probe_names"] = [p.strip() for p in parts[5:7]]
    # Autres routeurs de l'installation : blocs « IP(entier) US nom US … »
    # (un entier IPv4 seul, sans US, est l'adresse de la source de mesure : ignoré)
    ips: list[str] = []
    for p in parts:
        for m in re.finditer(rf"(\d{{8,10}}){US}", p):
            ip = int_to_ip(m.group(1))
            if ip:
                ips.append(ip)
    out["known_ips"] = sorted(set(ips))
    return out


def int_to_ip(value: Any) -> str | None:
    """Entier IPv4 du firmware (3232235977) → « 192.168.1.201 »."""
    val = to_int(value)
    if val is None or val < 16777216 or val > 4294967295:
        return None
    if str(value).strip() != str(val):
        return None
    return ".".join(str((val >> s) & 255) for s in (24, 16, 8, 0))


def known_ips_from_parafixe(cfg: dict) -> list[str]:
    """Routeurs déclarés dans la configuration (RMS_IP0…7, 17.xx)."""
    ips = []
    for i in range(8):
        ip = int_to_ip(cfg.get(f"RMS_IP{i}"))
        if ip:
            ips.append(ip)
    return sorted(set(ips))


# ------------------------------------------------------------------ planning
@dataclass
class Slot:
    start: int  # minutes depuis minuit
    end: int
    kind: str  # off / on / route
    raw_type: int
    threshold_w: int | None  # seuil Pw (routage)
    max_opening: int | None  # ouverture max % (routage triac) ou seuil haut (relais)
    on_opening: int | None  # ouverture d'une plage ON
    temp_channel: int  # -1 = aucune condition
    t_below: float | None  # condition T ≤
    t_above: float | None  # condition T ≥
    tarif_mask: int | None

    def as_dict(self) -> dict:
        return {
            "start": minutes_to_hhmm(self.start),
            "end": minutes_to_hhmm(self.end),
            "start_min": self.start,
            "end_min": self.end,
            "kind": self.kind,
            "threshold_w": self.threshold_w,
            "max_opening": self.max_opening,
            "on_opening": self.on_opening,
            "temp_channel": self.temp_channel,
            "t_below": self.t_below,
            "t_above": self.t_above,
            "tarif_mask": self.tarif_mask,
        }


def _temp_cond(value: Any) -> float | None:
    """Tinf/Tsup en dixièmes de °C ; > 1000 = pas de condition."""
    val = to_int(value)
    if val is None or val > 1000 or val < -500:
        return None
    return val / 10


def build_slots(periods: list[dict]) -> list[Slot]:
    slots: list[Slot] = []
    start = 0
    for p in periods:
        end = centi_hours_to_minutes(p.get("Hfin"))
        raw_type = to_int(p.get("Type")) or 1
        kind = SLOT_TYPES.get(raw_type, "off")
        channel = to_int(p.get("CanalTemp"))
        channel = -1 if channel is None else channel
        slots.append(
            Slot(
                start=start,
                end=end,
                kind=kind,
                raw_type=raw_type,
                threshold_w=to_int(p.get("Vmin")) if kind == "route" else None,
                max_opening=to_int(p.get("Vmax")) if kind == "route" else None,
                on_opening=to_int(p.get("ONouvre", 100)) if kind == "on" else None,
                temp_channel=channel,
                t_below=_temp_cond(p.get("Tinf")) if channel >= 0 else None,
                t_above=_temp_cond(p.get("Tsup")) if channel >= 0 else None,
                tarif_mask=to_int(p.get("Tarif")),
            )
        )
        start = end
    return slots


def slot_at(slots: list[Slot], minute_of_day: int) -> Slot | None:
    for s in slots:
        if s.start <= minute_of_day < s.end:
            return s
    return slots[-1] if slots else None


@dataclass
class ActionConfig:
    index: int
    title: str
    mode: str  # inactive / cut / multi_sine …
    mode_raw: int
    force_opening: int | None  # « Ouverture si forcée » (17.xx), None en 16.xx
    periods: list[dict] = field(default_factory=list)

    @property
    def is_triac(self) -> bool:
        return self.index == 0

    @property
    def on_off(self) -> bool:
        """Relais tout ou rien (pas d'ouverture progressive)."""
        return not self.is_triac and self.mode_raw == 1

    @property
    def slots(self) -> list[Slot]:
        return build_slots(self.periods)


def actions_from_parafixe(cfg: dict) -> list[ActionConfig]:
    out: list[ActionConfig] = []
    for i, a in enumerate(cfg.get("Actions") or []):
        mode_raw = to_int(a.get("Actif")) or 0
        out.append(
            ActionConfig(
                index=i,
                title=str(a.get("Titre") or f"Action {i}").strip(),
                mode=ACTION_MODES.get(mode_raw, "inactive"),
                mode_raw=mode_raw,
                force_opening=to_int(a.get("ForceOuvre")),
                periods=list(a.get("Periodes") or a.get("Périodes") or []),
            )
        )
    return out


def parse_actions_ajax(text: str) -> tuple[list[ActionConfig], list[str]]:
    """/ActionsAjax (16.xx) → actions + noms des 4 canaux de température.

    Par action (séparées par GS) : Actif, Titre, Host, Port, OrdreOn, OrdreOff, Repet,
    Tempo, Kp, Ki, Kd, PID, nombre de plages, puis 13 champs par plage.
    """
    groups = text.split(GS)
    head = groups[0].split(RS) if groups else []
    names = (_at(head, 1) or "").split(US)
    temp_names = [(n or "").strip() for n in (names + ["", "", "", ""])[:4]]
    out: list[ActionConfig] = []
    for idx, block in enumerate(g for g in groups[1:] if g.strip(RS + " \r\n|")):
        f = block.split(RS)
        if len(f) < len(ACTION_HEAD_FIELDS) + 1:
            continue
        head_vals = dict(zip(ACTION_HEAD_FIELDS, f))
        n = to_int(_at(f, len(ACTION_HEAD_FIELDS))) or 0
        base = len(ACTION_HEAD_FIELDS) + 1
        periods = []
        for k in range(n):
            vals = f[base + k * 13: base + (k + 1) * 13]
            if len(vals) < 13:
                break
            periods.append(dict(zip(PERIOD_FIELDS, vals)))
        mode_raw = to_int(head_vals.get("Actif")) or 0
        out.append(
            ActionConfig(
                index=idx,
                title=(head_vals.get("Titre") or f"Action {idx}").strip(),
                mode=ACTION_MODES.get(mode_raw, "inactive"),
                mode_raw=mode_raw,
                force_opening=None,
                periods=periods,
            )
        )
    return out, temp_names


# ------------------------------------------------------------------ mesures
def parse_ajax_data(text: str) -> dict:
    """/ajax_data : point de raccordement (« sonde maison ») + températures + tarif."""
    groups = text.split(GS)
    g0 = groups[0].split(RS) if groups else []
    house = groups[1].split(RS) if len(groups) > 1 else []
    data: dict[str, Any] = {
        "date": (_at(g0, 1) or "").strip() or None,
        "source": (_at(g0, 2) or "").strip() or None,
        "tariff": (_at(g0, 3) or "").strip() or None,
        "temperatures": parse_temperatures(_at(g0, 5) or ""),
        "grid_import_w": to_float(_at(house, 0)),
        "grid_export_w": to_float(_at(house, 1)),
    }
    imp, exp = data["grid_import_w"], data["grid_export_w"]
    data["grid_net_w"] = None if imp is None or exp is None else imp - exp
    return data


def parse_etat_actions(text: str) -> dict[int, dict]:
    """/ajax_etatActions : ouverture et forçage en cours des actions actives.

    Groupes : [températures, source, IP ext, nombre, action…] ; par action :
    numéro, titre, ouverture (% ou On/Off), minutes de forçage (+ marche, − arrêt).
    """
    groups = text.split(GS)
    out: dict[int, dict] = {}
    for rec in groups[4:]:
        f = rec.split(RS)
        if len(f) < 4 or not f[0].strip():
            continue
        idx = to_int(f[0])
        if idx is None:
            continue
        raw = f[2].strip()
        if raw.lower() == "on":
            opening = 100
        elif raw.lower() == "off":
            opening = 0
        else:
            opening = to_int(raw)
        out[idx] = {
            "index": idx,
            "name": f[1].strip(),
            "opening": opening,
            "force_min": to_int(f[3]) or 0,
        }
    return out


_MAC = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")


def parse_data_esp32(text: str) -> dict:
    """/ajax_dataESP32 : uptime, RSSI, MAC, IP, nom réseau, mémoire."""
    m = text.split(GS)[0].split(RS)
    ip_block = (_at(m, 7) or "").split(US)
    macs = [x.strip() for x in m if _MAC.match(x.strip())]
    return {
        "uptime_h": to_float(_at(m, 0)),
        "rssi": to_float(_at(m, 2)),
        # 1re MAC = point d'accès Wi-Fi, 2e = l'ESP32 (vérifié en 16.10)
        "mac": macs[1].lower() if len(macs) > 1 else (macs[0].lower() if macs else None),
        "ssid_present": bool((_at(m, 6) or "").strip()),
        "ip": ip_block[0].strip() if ip_block and ip_block[0].strip() else None,
        "hostname": ip_block[1].strip() if len(ip_block) > 1 and ip_block[1].strip() else None,
        "free_heap": to_float(_at(m, 13)),
    }


def redact(obj: Any) -> Any:
    """Masque les secrets d'une configuration (pour diagnostics et journaux)."""
    if isinstance(obj, dict):
        return {
            k: ("**REDACTED**" if SECRET_KEY_PATTERN.search(str(k)) and obj[k] not in ("", None) else redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def parse_json(text: str) -> dict | None:
    try:
        val = json.loads(text)
    except ValueError:
        return None
    return val if isinstance(val, dict) else None
