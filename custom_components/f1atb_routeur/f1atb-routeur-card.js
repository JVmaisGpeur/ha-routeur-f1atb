/*
 * Carte Lovelace « Routeur F1ATB » (ha-routeur-f1atb v1.0.0) – bilingue FR/EN.
 * type: custom:f1atb-routeur-card
 * entity: select.<routeur>_mode        (sélecteur de mode de l'intégration)
 * Blocs masqués par défaut : show_tiles, show_water, show_planning, show_mode, show_forcing, show_output
 */
const CARD_VERSION = "1.0.0";
const DOMAIN = "f1atb_routeur";
const BLOCKS = ["show_tiles", "show_water", "show_planning", "show_mode", "show_forcing", "show_output"];

const T = {
  fr: {
    online: "En ligne", offline: "Hors ligne", firmware: "firmware",
    modes: { off: "Arrêt", solar: "Solaire seul", solar_guarantee: "Solaire + garantie", forced: "Marche forcée", external: "Piloté" },
    piloted_by: "Piloté par", until: "jusqu'à", routed: "ROUTÉE", estimated: "estimée", measured: "mesurée",
    solar_today: "SOLAIRE AUJ.", solar_sub: "routé dans le ballon", grid_today: "RÉSEAU AUJ.", grid_sub: "rattrapage",
    water: "Ballon d'eau chaude", target: "consigne", hot: "Chaud", not_hot: "Pas encore chaud",
    method: { temperature: "sonde", thermostat: "sans sonde · thermostat", energy: "sans sonde · énergie" },
    thermo_open: "Thermostat : coupé", thermo_closed: "Thermostat : fermé", power: "Puissance ballon",
    boost_on: "Rattrapage en cours", boost_off: "Pas de rattrapage en cours",
    planning: "Planning du routeur", read_router: "lu dans le routeur", now: "maintenant",
    slot: { off: "OFF", on: "ON", route: "Routage" }, threshold: "seuil", rest: "Reste du jour",
    planning_note: "Horaires, seuil Pw et conditions se règlent dans le routeur.", open_router: "Ouvrir le routeur",
    mode: "Mode", mode_help: {
      off: "Arrêt : le chauffe-eau reste coupé (arrêts forcés de 30 min renouvelés).",
      solar: "Solaire seul : le routeur suit son planning, sans rattrapage.",
      solar_guarantee: "Solaire + garantie : routage du surplus, puis rattrapage en heures creuses si le ballon n'est pas chaud.",
      forced: "Marche forcée : chauffe à pleine puissance jusqu'à la fin de la durée.",
    },
    piloted_help: "Le pilote a la main : le mode reprendra quand il la rendra ou si elle expire (30 min sans renouvellement).",
    forcing: "Forçage manuel", duration: "Durée (min)", force_on: "Marche forcée", boost: "Rattrapage jusqu'à la consigne",
    cancel: "Annuler", forcing_note: "Retour automatique au mode choisi à la fin de la durée.",
    remaining: "Forçage en cours", min: "min",
    output: "Sortie et puissance", output_lbl: "Sortie du ballon", force_open: "Ouverture en marche forcée",
    origin: { declared: "déclarée", calibration: "calibrée par le compteur", meter: "mesurée (compteur dédié)" },
    calibrate: "Calibrer", opening: "Ouverture", triac: "Triac", relay: "Relais", no_entity: "Choisissez le sélecteur de mode d'un routeur F1ATB.",
    read_only: "Lecture seule",
  },
  en: {
    online: "Online", offline: "Offline", firmware: "firmware",
    modes: { off: "Off", solar: "Solar only", solar_guarantee: "Solar + guarantee", forced: "Forced on", external: "Controlled" },
    piloted_by: "Controlled by", until: "until", routed: "ROUTED", estimated: "estimated", measured: "measured",
    solar_today: "SOLAR TODAY", solar_sub: "routed to the tank", grid_today: "GRID TODAY", grid_sub: "boost",
    water: "Hot water tank", target: "target", hot: "Hot", not_hot: "Not hot yet",
    method: { temperature: "probe", thermostat: "no probe · thermostat", energy: "no probe · energy" },
    thermo_open: "Thermostat: open", thermo_closed: "Thermostat: closed", power: "Tank power",
    boost_on: "Boost running", boost_off: "No boost running",
    planning: "Router schedule", read_router: "read from the router", now: "now",
    slot: { off: "OFF", on: "ON", route: "Routing" }, threshold: "threshold", rest: "Rest of the day",
    planning_note: "Times, Pw threshold and conditions are set in the router.", open_router: "Open the router",
    mode: "Mode", mode_help: {
      off: "Off: the water heater stays off (30-min forced-off periods, renewed).",
      solar: "Solar only: the router follows its schedule, no boost.",
      solar_guarantee: "Solar + guarantee: surplus routing, then off-peak boost if the tank is not hot.",
      forced: "Forced on: full power until the end of the duration.",
    },
    piloted_help: "The controller is in charge: the mode resumes when it releases control or after 30 min without renewal.",
    forcing: "Manual forcing", duration: "Duration (min)", force_on: "Force on", boost: "Boost to target",
    cancel: "Cancel", forcing_note: "Automatic return to the chosen mode at the end of the duration.",
    remaining: "Forcing running", min: "min",
    output: "Output and power", output_lbl: "Tank output", force_open: "Forced opening",
    origin: { declared: "declared", calibration: "calibrated with the meter", meter: "measured (dedicated meter)" },
    calibrate: "Calibrate", opening: "Opening", triac: "Triac", relay: "Relay", no_entity: "Pick the mode selector of an F1ATB router.",
    read_only: "Read-only",
  },
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let LOCALE = undefined;
const num = (v, d = 1) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n.toLocaleString(LOCALE, { maximumFractionDigits: d, minimumFractionDigits: 0 }) : "–";
};

class F1atbRouteurCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._sig = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  static getConfigElement() {
    return document.createElement("f1atb-routeur-card-editor");
  }

  static getStubConfig(hass) {
    const sel = Object.values(hass.entities || {}).find((e) => e.platform === DOMAIN && e.translation_key === "operating_mode");
    return { entity: sel ? sel.entity_id : "" };
  }

  getCardSize() {
    return 2 + BLOCKS.filter((b) => this._config && this._config[b]).length * 3;
  }

  set hass(hass) {
    this._hass = hass;
    const ents = this._entities();
    const sig = JSON.stringify(Object.values(ents).map((id) => {
      const st = hass.states[id];
      return st ? [st.state, st.last_updated] : null;
    }));
    if (sig !== this._sig) {
      this._sig = sig;
      this._render();
    }
  }

  get _t() {
    const lang = (this._hass && (this._hass.locale?.language || this._hass.language)) || "fr";
    return lang.startsWith("fr") ? T.fr : T.en;
  }

  _entities() {
    const out = {};
    const hass = this._hass;
    if (!hass || !this._config?.entity) return out;
    const reg = hass.entities || {};
    const main = reg[this._config.entity];
    this._deviceId = main ? main.device_id : null;
    if (!this._deviceId) return out;
    for (const e of Object.values(reg)) {
      if (e.platform === DOMAIN && e.device_id === this._deviceId && e.translation_key) {
        if (!out[e.translation_key]) out[e.translation_key] = e.entity_id;
      }
    }
    return out;
  }

  _st(key) {
    const id = this._ents[key];
    return id ? this._hass.states[id] : undefined;
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const t = this._t;
    LOCALE = this._hass.locale?.language || this._hass.language || undefined;
    this._ents = this._entities();
    const c = this._config || {};
    if (!this._deviceId) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card><div class="pad muted">${esc(t.no_entity)}</div></ha-card>`;
      return;
    }
    const dev = (this._hass.devices || {})[this._deviceId] || {};
    const mode = this._st("operating_mode");
    const conn = this._st("connected");
    const fw = this._st("firmware");
    const ext = this._st("external_control");
    const online = conn && conn.state === "on";
    const modeVal = mode ? mode.state : "unknown";
    const extActive = ext && ext.state && ext.state !== "none" && ext.state !== "unavailable";
    const readOnly = fw && fw.attributes && fw.attributes.read_only;

    let html = `<ha-card><div class="card">`;
    html += `<div class="head">
      <div class="icon"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg></div>
      <div class="grow"><div class="title">${esc(dev.name_by_user || dev.name || "F1ATB")}</div>
      <div class="sub"><span class="dot ${online ? "on" : "off"}"></span>${online ? t.online : t.offline}${fw && fw.state && fw.state !== "unavailable" ? ` · ${t.firmware} ${esc(fw.state)}` : ""}${readOnly ? ` · ${t.read_only}` : ""}</div></div>
      <div class="chip">${esc(t.modes[modeVal] || modeVal)}</div></div>`;

    if (extActive) {
      const exp = ext.attributes.expires_at ? new Date(ext.attributes.expires_at) : null;
      const hh = exp ? exp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
      html += `<div class="banner"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>
        <div><div class="b">${t.piloted_by} ${esc(ext.state)}</div><div class="muted small">${esc((ext.attributes.controlled_keys || []).join(", "))}${hh ? ` · ${t.until} ${hh}` : ""}</div></div></div>`;
    }

    if (c.show_tiles) html += this._tiles(t);
    if (c.show_water) html += this._water(t);
    if (c.show_planning) html += this._planning(t, dev);
    if (c.show_mode) html += this._mode(t, modeVal, extActive);
    if (c.show_forcing) html += this._forcing(t, extActive);
    if (c.show_output) html += this._output(t);
    html += `</div></ha-card>`;
    this.shadowRoot.innerHTML = STYLE + html;
    this._bind();
  }

  _tiles(t) {
    const p = this._st("routed_power");
    const today = parseFloat(this._st("routed_energy_today")?.state);
    const grid = parseFloat(this._st("grid_energy_today")?.state);
    const solar = Number.isFinite(today) ? Math.max(0, today - (Number.isFinite(grid) ? grid : 0)) : NaN;
    const measured = p && p.attributes.measured;
    return `<div class="tiles">
      <div class="tile"><div class="lbl">${t.routed}</div><div class="val">${num(p?.state, 0)} <span>W</span></div><div class="muted small">${measured ? t.measured : t.estimated}</div></div>
      <div class="tile"><div class="lbl">${t.solar_today}</div><div class="val">${num(solar, 1)} <span>kWh</span></div><div class="muted small">${t.solar_sub}</div></div>
      <div class="tile"><div class="lbl">${t.grid_today}</div><div class="val">${num(grid, 1)} <span>kWh</span></div><div class="muted small">${t.grid_sub}</div></div></div>`;
  }

  _water(t) {
    const temp = this._st("water_temperature");
    const target = this._st("target_temperature");
    const reached = this._st("target_reached");
    const thermo = this._st("thermostat_open");
    const boost = this._st("boost_active");
    const power = this._st("water_heater_power");
    const method = reached?.attributes?.method || "temperature";
    let body = "";
    if (temp && temp.state !== "unavailable" && temp.state !== "unknown") {
      const tv = parseFloat(temp.state), tg = parseFloat(target?.state) || 55;
      const pct = Math.max(0, Math.min(100, ((tv - 15) / (tg - 15)) * 100));
      body += `<div class="row base"><div class="big">${num(tv, 1)} °C</div><div class="muted">${t.target} ${num(tg, 1)} °C</div></div>
        <div class="bar"><div style="width:${pct}%"></div></div>`;
    } else {
      body += `<div class="big2">${reached && reached.state === "on" ? t.hot : t.not_hot}</div>`;
    }
    body += `<div class="chips">
      <span class="pill">${thermo && thermo.state === "on" ? t.thermo_open : t.thermo_closed}</span>
      <span class="pill">${t.power} ${num(power?.state, 0)} W</span>
      <span class="pill">${boost && boost.state === "on" ? t.boost_on : t.boost_off}</span></div>`;
    return `<div class="block"><div class="row base"><div class="h">${t.water}</div><div class="muted small">${esc(t.method[method] || method)}</div></div>${body}</div>`;
  }

  _planning(t, dev) {
    const pl = this._st("planning");
    const slots = (pl && pl.attributes.slots) || [];
    const colors = { off: "#3b4556", on: "#e5604d", route: "#e3b341" };
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    let seg = "";
    for (const s of slots) {
      const w = ((s.end_min - s.start_min) / 1440) * 100;
      seg += `<div title="${esc(t.slot[s.kind])} ${esc(s.start)}–${esc(s.end)}" style="width:${w}%;background:${colors[s.kind] || colors.off}"></div>`;
    }
    let list = "";
    for (const s of slots.filter((x) => x.kind !== "off")) {
      const cond = [];
      if (s.kind === "route" && s.threshold_w !== null) cond.push(`${t.threshold} ${s.threshold_w} W`);
      if (s.kind === "on" && s.on_opening !== null) cond.push(`${s.on_opening} %`);
      if (s.t_below !== null) cond.push(`T ≤ ${num(s.t_below, 1)} °C`);
      if (s.t_above !== null) cond.push(`T ≥ ${num(s.t_above, 1)} °C`);
      list += `<div class="slot"><span class="sq" style="background:${colors[s.kind]}"></span><span class="hrs">${esc(s.start)} – ${esc(s.end)}</span><span class="muted">${esc(t.slot[s.kind])}${cond.length ? " · " + esc(cond.join(" · ")) : ""}</span></div>`;
    }
    const cur = pl && pl.attributes.current;
    if (cur) list += `<div class="slot"><span class="sq" style="background:#fff"></span><span class="hrs">${now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span><span class="muted">${t.now} · ${esc(t.slot[cur.kind])}</span></div>`;
    const url = dev.configuration_url ? `${dev.configuration_url.replace(/\/$/, "")}/Actions` : null;
    return `<div class="block"><div class="row base"><div class="h">${t.planning}</div><div class="muted small">${t.read_router}</div></div>
      <div class="frise">${seg}<div class="nowline" style="left:${(nowMin / 1440) * 100}%"></div></div>
      <div class="ticks"><span>0 h</span><span>6 h</span><span>12 h</span><span>18 h</span><span>24 h</span></div>
      <div class="slots">${list}</div>
      <div class="muted small">${t.planning_note}${url ? ` <a href="${esc(url)}" target="_blank" rel="noreferrer">${t.open_router}</a>` : ""}</div></div>`;
  }

  _mode(t, modeVal, ext) {
    const opts = ["off", "solar", "solar_guarantee", "forced"];
    const btns = opts.map((o) => `<button class="mbtn ${o === modeVal && !ext ? "sel" : ""}" data-mode="${o}" ${ext ? "disabled" : ""}>${esc(t.modes[o])}</button>`).join("");
    const help = ext ? t.piloted_help : t.mode_help[modeVal] || "";
    return `<div class="block"><div class="h">${t.mode}</div><div class="grid2">${btns}</div><div class="muted small">${esc(help)}</div></div>`;
  }

  _forcing(t, ext) {
    const rem = parseInt(this._st("force_remaining")?.state, 10);
    const info = Number.isFinite(rem) && rem !== 0 ? `<div class="muted small">${t.remaining} : ${rem > 0 ? "+" : ""}${rem} ${t.min}</div>` : "";
    const fo = this._st("force_opening");
    const foVal = fo && !["unavailable", "unknown"].includes(fo.state) ? parseInt(fo.state, 10) : null;
    const slider = foVal === null ? "" : `<div class="lab"><div class="row base"><span>${t.force_open}</span><span class="pct">${foVal} %</span></div>
      <input id="fo" class="range" type="range" min="5" max="100" step="1" value="${foVal}" aria-label="${esc(t.force_open)}"></div>`;
    return `<div class="block"><div class="h">${t.forcing}</div>${slider}
      <label class="lab">${t.duration}<input id="dur" type="number" min="1" max="1440" value="${this._dur || 60}"></label>
      <div class="row gap"><button class="act red" data-act="force" ${ext ? "disabled" : ""}>${t.force_on}</button>
      <button class="act" data-act="boost" ${ext ? "disabled" : ""}>${t.boost}</button>
      <button class="act" data-act="cancel" ${ext ? "disabled" : ""}>${t.cancel}</button></div>
      ${info}<div class="muted small">${t.forcing_note}</div></div>`;
  }

  _output(t) {
    const op = this._st("opening");
    const power = this._st("water_heater_power");
    const kind = op?.attributes?.is_triac ? t.triac : op ? t.relay : "";
    const origin = power?.attributes?.origin || "declared";
    return `<div class="block"><div class="h">${t.output}</div>
      <div class="kv"><span class="muted">${t.output_lbl}</span><span>${esc(op?.attributes?.action || "–")}${kind ? " · " + kind : ""}</span></div>
      <div class="kv"><span class="muted">${t.opening}</span><span>${num(op?.state, 0)} %</span></div>
      <div class="kv"><span class="muted">${t.power}</span><span>${num(power?.state, 0)} W · ${esc(t.origin[origin] || origin)}</span></div>
      <div class="row gap"><button class="act blue" data-act="calibrate">${t.calibrate}</button></div></div>`;
  }

  _bind() {
    const root = this.shadowRoot;
    const fo = root.getElementById("fo");
    if (fo) {
      const pct = root.querySelector(".pct");
      fo.addEventListener("input", () => { if (pct) pct.textContent = `${fo.value} %`; });
      fo.addEventListener("change", () => {
        const id = this._ents.force_opening;
        if (id) this._hass.callService("number", "set_value", { entity_id: id, value: parseInt(fo.value, 10) });
      });
    }
    const dur = root.getElementById("dur");
    if (dur) dur.addEventListener("input", () => { this._dur = parseInt(dur.value, 10) || 60; });
    root.querySelectorAll("[data-mode]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = this._ents.operating_mode;
        if (id) this._hass.callService("select", "select_option", { entity_id: id, option: b.dataset.mode });
      }),
    );
    root.querySelectorAll("[data-act]").forEach((b) =>
      b.addEventListener("click", () => {
        const dur = parseInt(root.getElementById("dur")?.value, 10) || 60;
        const dev = this._deviceId;
        const act = b.dataset.act;
        if (act === "force") this._hass.callService(DOMAIN, "set_mode", { device_id: dev, mode: "forced", duration: dur });
        if (act === "boost") this._hass.callService(DOMAIN, "boost", { device_id: dev, duration: dur });
        if (act === "cancel") {
          this._hass.callService(DOMAIN, "cancel_boost", { device_id: dev });
          const mode = this._st("operating_mode");
          if (mode && mode.state === "forced") {
            this._hass.callService(DOMAIN, "set_mode", { device_id: dev, mode: mode.attributes.prev_mode || "solar" });
          }
        }
        if (act === "calibrate" && this._ents.calibrate) this._hass.callService("button", "press", { entity_id: this._ents.calibrate });
      }),
    );
  }
}

const STYLE = `<style>
  :host { --bg:#141922; --surf:#1b212d; --line:#2a3240; --ink:#e8ecf2; --mute:#a7b0bd; --accent:#4c8dff; }
  ha-card { background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 20px; overflow: hidden; }
  .card { padding: 18px; display: flex; flex-direction: column; gap: 14px; font-family: Inter, var(--paper-font-body1_-_font-family, system-ui), sans-serif; }
  .pad { padding: 16px; }
  .head { display: flex; align-items: center; gap: 12px; }
  .icon { width: 44px; height: 44px; border-radius: 12px; background: #1d2430; display: flex; align-items: center; justify-content: center; }
  .icon svg { width: 26px; height: 26px; fill: none; stroke: #e3b341; stroke-width: 1.8; stroke-linecap: round; }
  .grow { flex: 1; min-width: 0; }
  .title { font-size: 17px; font-weight: 700; }
  .sub { font-size: 12.5px; color: var(--mute); display: flex; align-items: center; gap: 6px; }
  .dot { width: 8px; height: 8px; border-radius: 4px; display: inline-block; }
  .dot.on { background: #3fb67a; } .dot.off { background: #e5604d; }
  .chip { padding: 6px 12px; border-radius: 999px; background: #1d2a44; color: #b9d0ff; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .banner { border: 1px solid #3a4a6b; background: #17203a; border-radius: 14px; padding: 10px 12px; display: flex; gap: 10px; }
  .banner svg { width: 20px; height: 20px; fill: none; stroke: #8fb6ff; stroke-width: 1.8; flex-shrink: 0; margin-top: 2px; }
  .b { font-size: 14px; font-weight: 600; }
  .tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .tile, .block { background: var(--surf); border-radius: 14px; padding: 12px; }
  .block { display: flex; flex-direction: column; gap: 10px; padding: 14px; }
  .lbl { font-size: 11px; font-weight: 600; letter-spacing: .04em; color: var(--mute); }
  .val { font-size: 21px; font-weight: 700; margin-top: 4px; } .val span { font-size: 12px; color: var(--mute); }
  .h { font-size: 15px; font-weight: 600; }
  .row { display: flex; justify-content: space-between; align-items: center; } .row.base { align-items: baseline; } .row.gap { gap: 8px; justify-content: flex-start; flex-wrap: wrap; }
  .big { font-size: 30px; font-weight: 700; } .big2 { font-size: 22px; font-weight: 700; }
  .bar { height: 8px; border-radius: 4px; background: var(--line); overflow: hidden; } .bar div { height: 8px; background: #e3b341; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .pill { padding: 5px 10px; border-radius: 999px; background: #232b38; font-size: 12px; color: #d5dbe4; }
  .muted { color: var(--mute); } .small { font-size: 12px; line-height: 1.45; }
  .frise { position: relative; height: 30px; border-radius: 8px; overflow: hidden; display: flex; }
  .frise > div:not(.nowline) { height: 30px; border-right: 1px solid var(--bg); box-sizing: border-box; }
  .nowline { position: absolute; top: 0; bottom: 0; width: 2px; background: #fff; }
  .ticks { display: flex; justify-content: space-between; font-size: 11px; color: var(--mute); }
  .slots { display: flex; flex-direction: column; gap: 5px; }
  .slot { display: flex; gap: 10px; align-items: center; font-size: 13px; }
  .sq { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .hrs { width: 104px; color: #d5dbe4; }
  .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  button { font-family: inherit; cursor: pointer; }
  .mbtn, .act { min-height: 42px; border-radius: 10px; border: 1px solid #3a4454; background: transparent; color: var(--ink); font-size: 13px; font-weight: 600; padding: 0 14px; }
  .mbtn.sel { border: 0; background: var(--accent); color: #fff; }
  button:disabled { color: #7d8796; cursor: not-allowed; }
  .act.red { background: #e5604d; border: 0; color: #fff; } .act.blue { border-color: var(--accent); color: #b9d0ff; }
  .lab { display: flex; flex-direction: column; gap: 6px; font-size: 12px; color: var(--mute); }
  input { height: 42px; box-sizing: border-box; border-radius: 10px; border: 1px solid #2f3848; background: #121720; color: var(--ink); padding: 0 12px; font-size: 15px; font-family: inherit; }
  input.range { height: 28px; padding: 0; background: transparent; border: 0; accent-color: var(--accent); width: 100%; }
  .pct { color: var(--ink); font-weight: 600; }
  .kv { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
  a { color: #8fb6ff; }
</style>`;

class F1atbRouteurCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    const fr = (this._hass.locale?.language || this._hass.language || "fr").startsWith("fr");
    const labels = fr
      ? { entity: "Routeur (sélecteur de mode)", show_tiles: "Tuiles (puissance, énergies)", show_water: "Ballon", show_planning: "Planning", show_mode: "Mode", show_forcing: "Forçage manuel", show_output: "Sortie et puissance" }
      : { entity: "Router (mode selector)", show_tiles: "Tiles (power, energy)", show_water: "Water tank", show_planning: "Schedule", show_mode: "Mode", show_forcing: "Manual forcing", show_output: "Output and power" };
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [
      { name: "entity", selector: { entity: { domain: "select", integration: DOMAIN } } },
      ...BLOCKS.map((b) => ({ name: b, selector: { boolean: {} } })),
    ];
    this._form.computeLabel = (s) => labels[s.name] || s.name;
    this._form.data = this._config;
  }
}

if (!customElements.get("f1atb-routeur-card")) customElements.define("f1atb-routeur-card", F1atbRouteurCard);
if (!customElements.get("f1atb-routeur-card-editor")) customElements.define("f1atb-routeur-card-editor", F1atbRouteurCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "f1atb-routeur-card")) {
  window.customCards.push({
    type: "f1atb-routeur-card",
    name: "Routeur F1ATB",
    description: "Routeur solaire F1ATB : mode, ballon, planning, forçage / F1ATB solar router",
    preview: false,
  });
}
console.info(`%c F1ATB-ROUTEUR-CARD %c v${CARD_VERSION} `, "background:#e3b341;color:#141922;font-weight:700", "background:#141922;color:#e3b341");
