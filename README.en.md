# F1ATB router for Home Assistant

🇫🇷 [Version française](README.md)

Home Assistant integration to control an **F1ATB solar router** locally (RMS on ESP32, unmodified official firmware). It works on its own, or under an external controller (automation or another integration) through a generic take-over interface.

- Reads the router's measurements, schedule and output state.
- Modes: **Off**, **Solar only**, **Solar + guarantee** (off-peak boost when the sun was not enough), **Forced on**.
- "Water hot" from a probe, from the thermostat cut-off, or from the heating energy.
- Water heater power declared, measured by a dedicated meter, or calibrated with the surplus meter.
- External control that expires by itself after 30 min without renewal, with its reason shown on the card.
- **Control the router / Display only** switch: Home Assistant can just show the router's data without sending it anything.
- Lovelace card included, French / English.

> Independent project, not affiliated with F1ATB. Thanks to F1ATB for the router, and to [WillSpecIm/Integration-f1atb](https://github.com/WillSpecIm/Integration-f1atb) for documenting the API.

## Compatibility

| Firmware | Features |
| --- | --- |
| 17.xx (verified on 17.30) | All |
| 16.xx (verified on 16.10) | All; forced-on always runs at 100% (no "forced opening"); each On press adds 30 min, Off stops everything, one On press cancels a forced-off |
| Other versions | Read-only (measurements, schedule) and a repair notice: open an issue with the diagnostics |

The version is detected automatically. Home Assistant 2024.11 or later.

## What the integration sends to the router

For control, only **30-minute temporary forcings**, counted down by the router itself (`/ForceAction` on 17.xx, home page On/Off buttons on 16.xx). Control **never writes** the router configuration: times, Pw threshold, conditions and waveform stay your settings, made in the router web interface.

Single exception, on 17.xx: the **forced-on opening** ("Ouverture si forcée") can be set from Home Assistant. It is saved in the router only when you change it yourself, never by automatic control. If Home Assistant stops, the router resumes its schedule within 30 min.

The router does not measure its outputs' power, only the grid connection point (Shelly, Linky, clamp…). Without a dedicated water heater meter, routed power is therefore **estimated** (opening × water heater power).

## Installation

1. HACS → ⋮ menu → **Custom repositories** → `https://github.com/JVmaisGpeur/ha-routeur-f1atb`, category **Integration**.
2. Install **Routeur F1ATB**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → Routeur F1ATB**, then:
   - **Search the network**: the integration scans your local network (up to 1024 addresses) and lists the F1ATB routers found. Tick the ones to add: the first is set up right away, the others appear under **Discovered** to be confirmed one by one;
   - **Enter the IP address** if the search finds nothing.

   Routers seen by DHCP (hostname `RMS-ESP32-…`) and those known by a router already added are offered under **Discovered** too. Each must be confirmed; "Ignore": it is not offered again.

The search only reads each address's home page: it calls no other page and sends no command.

### Configuration

One question per screen, and only the ones that apply to you:

1. **Water heater output**: asked only if the router has several active outputs.
2. **Water temperature**: router probe (picked automatically when there is only one), Home Assistant sensor, or **No probe**.
3. Without a probe only: **when is the water hot?** Thermostat cut-off (simplest) or after a heating energy. Target and safety temperature are then not asked.
4. **Water heater power**: rating plate, dedicated meter, or calibration after setup.
5. **Off-peak hours**: start and end (the guarantee aims for the end of off-peak hours), and the target when there is a probe. If your schedule already has an ON slot, the integration starts in "Solar only" so as not to heat twice.

**Options**, in three sections: *Water heater* (same questions), *Off-peak hours and target* (hysteresis, deadline, optional off-peak entity), *Advanced* (external control, maximum forced-on duration, grid sensor, polling interval, firmware format, safety temperature).

### Recommended router settings

- A **wide ROUTING slot**, e.g. 8:00–20:00: the integration (or a controller) can always cut a slot with a forced-off, but cannot create one.
- With batteries regulating the grid point: a **Pw threshold at least 20 W below the batteries' target** (e.g. −20 to −50 W for a 0 W target), so the batteries take the surplus first.

## Control or display only

The **Control the router** switch (also on the card) sets Home Assistant's role:

- **on** (default): the integration and external controllers can command the router;
- **off, "Display only"**: the integration releases the router (it cancels its own running forcing once), then sends nothing. Measurements, schedule and state stay visible. Control services are refused with a clear message, and an external controller holding control loses it.

The Chef d'orchestre énergie (or any other controller) reads this switch, key `control_enabled`, to know whether it may command the router.

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
| `sensor` Status | What the water heater is doing, in one sentence: `solar`, `waiting_surplus`, `on_slot`, `boost`, `forced`, `off`, `blocked`, `hot`, `idle`, `safety` (attributes: power, temperature, target, controller, reason, slot end…) |
| `switch` Control the router | On: control; off: display only |
| `select` Mode | Operating mode (attributes `user_mode`, `controller`, `reason`) |
| `sensor` Routed power | Measured (dedicated meter) or estimated |
| `sensor` Routed energy today / total | Total works with the Energy dashboard |
| `sensor` Grid energy (boost) today | Energy heated during a forced-on or an ON slot |
| `sensor` Water temperature | When a probe is configured |
| `sensor` Opening, Forcing remaining, Current slot | Output state and schedule (`slots` attribute) |
| `sensor` External control | Controller name (attributes `controller`, `controlled_keys`, `expires_at`, `reason`) |
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
    reason: "Batteries first"
- action: f1atb_routeur.set_mode
  data:
    device_id: !input router
    mode: "off"
    controller: "My controller"
    reason: "Batteries first"
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input router
    active: false
    controller: "My controller"
```

The optional `reason` is shown on the card: "Blocked by My controller – Batteries first".

A user call on a setting held by a controller is refused, unless `override: true`, which ends the external control. All control services are refused in "Display only".

## Card

The `custom:f1atb-routeur-card` card loads automatically. Add it from the dashboard ("Routeur F1ATB"). It always shows the router name, the **Control / Display only** switch and a sentence saying what the water heater is doing ("Heating with solar surplus – 1,240 W sent to the tank until 20:00", "Blocked by Chef d'orchestre énergie – Batteries first"…). Three optional blocks are turned on in the editor:

| Key | Block |
| --- | --- |
| `show_tiles` | Power to the tank, today's solar and grid energy |
| `show_controls` | "What should the water heater do?" (4 explained modes), forced-on duration and opening, "Heat now", "Stop and return to the schedule" |
| `show_planning` | Router schedule in plain words ("Heats with solar surplus up to 60 °C") |

```yaml
type: custom:f1atb-routeur-card
entity: select.ecs_f1atb_mode
show_tiles: true
show_controls: true
show_planning: true
```

Controls are hidden in "Display only", offline or read-only, and locked while an external controller holds control. Setup settings (probe, power…) are under **Device settings**, at the bottom of the card.

## Known limits (v1.1.0)

- Pw threshold, times and waveform are read but not changed from Home Assistant (router settings). The waveform is not shown on the card.
- Only the output feeding the water heater is handled; the router's other outputs do not appear.
- Forced-on runs at the "forced opening" (adjustable on 17.xx) or 100% (16.xx); no forced-on at a given power in W.
- Without a probe or a dedicated meter, the thermostat cut-off is inferred from an export jump at the meter: approximate (a passing cloud can fool it).
- If batteries offset the load during calibration, the measured difference is wrong: stop them for a few seconds, or declare the power.
- Do not expose the router to the Internet: its API has no authentication and its configuration holds your passwords in clear text. The integration neither stores nor logs them, and redacts them in diagnostics.

## License

MIT – © 2026 JVmaisGpeur
