# F1ATB router for Home Assistant

🇫🇷 [Version française](README.md)

Home Assistant integration to control an **F1ATB solar router** locally (RMS on ESP32, unmodified official firmware). It works on its own, or under an external controller (automation or another integration) through a generic take-over interface.

- Reads the router's measurements, schedule and output state.
- Modes: **Off**, **Solar only**, **Solar + guarantee** (off-peak boost when the sun was not enough), **Forced on**.
- "Water hot" from a probe, from the thermostat cut-off, or from the heating energy.
- Water heater power declared, measured by a dedicated meter, or calibrated with the surplus meter.
- External control that expires by itself after 30 min without renewal.
- Lovelace card included, French / English.

> Independent project, not affiliated with F1ATB. Thanks to F1ATB for the router, and to [WillSpecIm/Integration-f1atb](https://github.com/WillSpecIm/Integration-f1atb) for documenting the API.

## Compatibility

| Firmware | Features |
| --- | --- |
| 17.xx (verified on 17.30) | All |
| 16.xx (verified on 16.10) | All; forced-on always runs at 100% (no "forced opening"); a forced-off cannot be cancelled and expires by itself within 30 min |
| Other versions | Read-only (measurements, schedule) and a repair notice: open an issue with the diagnostics |

The version is detected automatically. Home Assistant 2024.11 or later.

## What the integration sends to the router

For control, only **30-minute temporary forcings**, counted down by the router itself (`/ForceAction` on 17.xx, home page On/Off buttons on 16.xx). Control **never writes** the router configuration: times, Pw threshold, conditions and waveform stay your settings, made in the router web interface.

Single exception, on 17.xx: the **forced-on opening** ("Ouverture si forcée") can be set from Home Assistant. It is saved in the router only when you change it yourself, never by automatic control. If Home Assistant stops, the router resumes its schedule within 30 min.

The router does not measure its outputs' power, only the grid connection point (Shelly, Linky, clamp…). Without a dedicated water heater meter, routed power is therefore **estimated** (opening × water heater power).

## Installation

1. HACS → ⋮ menu → **Custom repositories** → `https://github.com/JVmaisGpeur/ha-routeur-f1atb`, category **Integration**.
2. Install **Routeur F1ATB**, then restart Home Assistant.
3. **Settings → Devices & services**:
   - routers found on the network (hostname `RMS-ESP32-…`) show up under **Discovered**;
   - once a first router is added, the routers it knows (declared in its configuration) are offered too;
   - otherwise **Add integration → Routeur F1ATB** and enter the IP address.

   Every discovered router must be confirmed (name, address, firmware, outputs). "Ignore": it is not offered again.

A router whose fixed IP is set in the router itself (no DHCP) is not seen by discovery: add it by its address.

### Configuration

**Water heater**: output feeding it (triac or relay), temperature source (router probe, Home Assistant sensor or none), power source (declared, dedicated meter, calibration) and "water hot" method (temperature, thermostat cut-off, heating energy).

**Standalone operation**: target (55 °C by default), off-peak hours (optional entity, or times), guarantee deadline. If your schedule already has an ON slot (boost done by the router), the integration starts in "Solar only" so as not to heat twice.

**Options**: hysteresis, safety temperature (65 °C, stops any forcing), maximum manual forced-on duration, allow external control, optional grid power sensor, polling interval, firmware format (fallback).

### Recommended router settings

- A **wide ROUTING slot**, e.g. 8:00–20:00: the integration (or a controller) can always cut a slot with a forced-off, but cannot create one.
- With batteries regulating the grid point: a **Pw threshold at least 20 W below the batteries' target** (e.g. −20 to −50 W for a 0 W target), so the batteries take the surplus first.

## Modes

| Mode | Behaviour |
| --- | --- |
| Off | 30-min forced-off periods, renewed: the water heater stays off |
| Solar only | The router follows its schedule; the integration sends nothing |
| Solar + guarantee | Router schedule; then, between the off-peak start and the deadline, forced on until the water is hot. Event `f1atb_routeur_target_missed` if the target is not reached at the deadline |
| Forced on | Forced on for the chosen duration (12 h max), then back to the previous mode |
| Controlled | Set automatically when an external controller holds the mode |

Priorities: thermal safety → user action with `override` → external controller → standalone rules.

## Entities

| Entity | Role |
| --- | --- |
| `select` Mode | Operating mode |
| `sensor` Routed power | Measured (dedicated meter) or estimated |
| `sensor` Routed energy today / total | Total works with the Energy dashboard |
| `sensor` Grid energy (boost) today | Energy heated during a forced-on or an ON slot |
| `sensor` Water temperature | When a probe is configured |
| `sensor` Opening, Forcing remaining, Current slot | Output state and schedule (`slots` attribute) |
| `sensor` External control | Controller name (attributes `controller`, `controlled_keys`, `expires_at`) |
| `number` Target, Water heater power | Settings |
| `number` Forced opening (17.xx) | Opening during a forced-on, saved in the router when you change it |
| `binary_sensor` Connected, Water hot, Boost running, Thermostat open | |
| `button` Calibrate power | Short forced-on and measurement of the grid difference |

Diagnostics: today's tariff, firmware, Wi-Fi signal, uptime, other probes.

## Services

| Service | Role |
| --- | --- |
| `f1atb_routeur.set_mode` | Set the mode (`duration` for forced on) |
| `f1atb_routeur.boost` / `cancel_boost` | One-off boost (duration, energy or temperature) |
| `f1atb_routeur.set_target_temperature` | Target |
| `f1atb_routeur.calibrate` | Power calibration |
| `f1atb_routeur.set_external_control` | Take-over by an external controller |

### External control

A controller (automation, other integration) takes over some settings (`mode`, `boost`, `target_temperature`) and must **renew within 30 min**; otherwise control expires, the `f1atb_routeur_external_control_expired` event fires and the router returns to its mode. Settings not taken over keep following the standalone rules.

```yaml
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input router
    active: true
    controller: "My controller"
    controlled_keys: [mode]
- action: f1atb_routeur.set_mode
  data:
    device_id: !input router
    mode: "off"
    controller: "My controller"
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input router
    active: false
    controller: "My controller"
```

A user call on a setting held by a controller is refused, unless `override: true`, which ends the external control.

## Card

The `custom:f1atb-routeur-card` card loads automatically. Add it from the dashboard ("Routeur F1ATB") and turn its blocks on in the editor (all hidden by default):

```yaml
type: custom:f1atb-routeur-card
entity: select.ecs_f1atb_mode
show_tiles: true
show_water: true
show_planning: true
show_mode: true
show_forcing: true
show_output: true
```

## Known limits (v1.0.0)

- Pw threshold, times and waveform are read but not changed from Home Assistant (router settings). The waveform is not shown on the card.
- Only the output feeding the water heater is handled; the router's other outputs do not appear.
- Forced-on runs at the "forced opening" (adjustable on 17.xx) or 100% (16.xx); no forced-on at a given power in W.
- Without a probe or a dedicated meter, the thermostat cut-off is inferred from an export jump at the meter: approximate (a passing cloud can fool it).
- If batteries offset the load during calibration, the measured difference is wrong: stop them for a few seconds, or declare the power.
- Do not expose the router to the Internet: its API has no authentication and its configuration holds your passwords in clear text. The integration neither stores nor logs them, and redacts them in diagnostics.

## License

MIT – © 2026 JVmaisGpeur
