/*
 * Carte Lovelace « Routeur F1ATB » (ha-routeur-f1atb v1.1.0) – bilingue FR/EN.
 * type: custom:f1atb-routeur-card
 * entity: select.<routeur>_mode          (sélecteur de mode de l'intégration)
 * Blocs facultatifs (masqués par défaut) : show_tiles, show_controls, show_planning
 * Toujours affichés : en-tête, interrupteur Piloter / Affichage seulement, phrase d'état.
 */
const CARD_VERSION = "1.1.0";
const DOMAIN = "f1atb_routeur";
const BLOCKS = ["show_tiles", "show_controls", "show_planning"];

const T = {
  fr: {
    online: "En ligne", offline: "Hors ligne", firmware: "firmware",
    modes: { off: "Arrêt", solar: "Solaire seul", solar_guarantee: "Solaire + garantie", forced: "Marche forcée", external: "Piloté" },
    mode_sub: { off: "Ne chauffe jamais", solar: "Surplus solaire uniquement", solar_guarantee: "Surplus, puis nuit si pas chaud", forced: "Pleine puissance pendant une durée" },
    pilot: "Piloter le routeur", display: "Affichage seulement",
    pilot_help: "Home Assistant et les pilotes (ex. Chef d'orchestre) peuvent commander le routeur.",
    display_help: "Home Assistant affiche les infos du routeur sans rien lui envoyer.",
    st: {
      offline: ["Routeur hors ligne", "Pas de réponse du routeur : il reprend seul son planning."],
      solar: ["Chauffe avec le surplus solaire", "{power} W envoyés au ballon{slotEnd}"],
      waiting_surplus: ["Attend du surplus solaire", "Plage de routage{slotEnd} · rien à router pour l'instant"],
      on_slot: ["Chauffe sur le réseau (plage ON)", "{power} W{slotEnd}"],
      boost: ["Rattrapage jusqu'à {targetTxt}", "{tempTxt}{power} W envoyés au ballon"],
      forced: ["Marche forcée", "{power} W{untilTxt}"],
      off: ["Arrêt : ne chauffe pas", "Arrêt forcé renouvelé tant que ce mode est choisi"],
      blocked: ["Bloqué par {controller}", "{reasonTxt}{untilTxt}"],
      hot: ["Ballon chaud, ne chauffe plus", "{tempOrThermo}"],
      idle: ["Ne chauffe pas", "Plage OFF du routeur{slotEnd}"],
      safety: ["Sécurité : eau trop chaude", "{tempTxt}plus aucune marche forcée"],
    },
    until: " · jusqu'à ", slot_until: " jusqu'à ", now_temp: "{t} °C maintenant · ", hot_target: "ballon chaud",
    thermo: "Le thermostat a coupé", display_line: "Affichage seulement : aucune commande n'est envoyée.",
    to_ball: "VERS LE BALLON", now: "en ce moment", measured: "mesurée", estimated: "estimée",
    solar_today: "SOLAIRE AUJ.", free: "gratuit", grid_today: "RÉSEAU AUJ.", grid_sub: "rattrapage",
    what: "Que doit faire le chauffe-eau ?", piloted: "piloté",
    locked_help: "{controller} a la main. Ton choix reprendra quand il la rendra, ou au plus tard 30 min après s'il cesse de la renouveler.",
    during: "Pendant", until2: "jusqu'à", fo: "Ouverture en marche forcée",
    heat_now: "Chauffer maintenant jusqu'à {targetTxt}", heat_sub: "Pleine puissance sur le réseau, s'arrête dès que le ballon est chaud",
    stop: "Arrêter et revenir au planning du routeur",
    planning: "Planning du routeur", set_in_router: "réglé dans le routeur",
    slot_on: "Chauffe sur le réseau", slot_route: "Chauffe avec le surplus solaire", slot_off: "Ne chauffe pas",
    if_below: " si l'eau est sous {t} °C", up_to: " jusqu'à {t} °C", at_pct: " à {p} %", threshold: "seuil {w} W",
    open_router: "Ouvrir le routeur", settings: "Réglages de l'appareil", no_entity: "Choisissez le sélecteur de mode d'un routeur F1ATB.",
    less: "30 minutes de moins", more: "30 minutes de plus", rest: "Reste du jour",
  },
  en: {
    online: "Online", offline: "Offline", firmware: "firmware",
    modes: { off: "Off", solar: "Solar only", solar_guarantee: "Solar + guarantee", forced: "Forced on", external: "Controlled" },
    mode_sub: { off: "Never heats", solar: "Solar surplus only", solar_guarantee: "Surplus, then night if not hot", forced: "Full power for a duration" },
    pilot: "Control the router", display: "Display only",
    pilot_help: "Home Assistant and controllers (e.g. Chef d'orchestre) can command the router.",
    display_help: "Home Assistant shows the router's data without sending it anything.",
    st: {
      offline: ["Router offline", "No answer from the router: it keeps following its own schedule."],
      solar: ["Heating with solar surplus", "{power} W sent to the tank{slotEnd}"],
      waiting_surplus: ["Waiting for solar surplus", "Routing slot{slotEnd} · nothing to route yet"],
      on_slot: ["Heating from the grid (ON slot)", "{power} W{slotEnd}"],
      boost: ["Boost up to {targetTxt}", "{tempTxt}{power} W sent to the tank"],
      forced: ["Forced on", "{power} W{untilTxt}"],
      off: ["Off: not heating", "Forced-off renewed while this mode is selected"],
      blocked: ["Blocked by {controller}", "{reasonTxt}{untilTxt}"],
      hot: ["Tank hot, not heating", "{tempOrThermo}"],
      idle: ["Not heating", "Router OFF slot{slotEnd}"],
      safety: ["Safety: water too hot", "{tempTxt}no more forced-on"],
    },
    until: " · until ", slot_until: " until ", now_temp: "{t} °C now · ", hot_target: "tank hot",
    thermo: "The thermostat cut off", display_line: "Display only: no command is sent.",
    to_ball: "TO THE TANK", now: "right now", measured: "measured", estimated: "estimated",
    solar_today: "SOLAR TODAY", free: "free", grid_today: "GRID TODAY", grid_sub: "boost",
    what: "What should the water heater do?", piloted: "controlled",
    locked_help: "{controller} is in charge. Your choice resumes when it releases control, or 30 min after it stops renewing.",
    during: "For", until2: "until", fo: "Forced-on opening",
    heat_now: "Heat now up to {targetTxt}", heat_sub: "Full power from the grid, stops as soon as the tank is hot",
    stop: "Stop and return to the router schedule",
    planning: "Router schedule", set_in_router: "set in the router",
    slot_on: "Heats from the grid", slot_route: "Heats with solar surplus", slot_off: "Does not heat",
    if_below: " if water is below {t} °C", up_to: " up to {t} °C", at_pct: " at {p}%", threshold: "threshold {w} W",
    open_router: "Open the router", settings: "Device settings", no_entity: "Pick the mode selector of an F1ATB router.",
    less: "30 minutes less", more: "30 minutes more", rest: "Rest of the day",
  },
};

const COLORS = {
  solar: ["#e3b341", "#1f1d14", "#4a4226"], waiting_surplus: ["#a7b0bd", "#1b212d", "#2f3848"], on_slot: ["#e5604d", "#241817", "#5a2f29"],
  boost: ["#e5604d", "#241817", "#5a2f29"], forced: ["#e5604d", "#241817", "#5a2f29"], off: ["#a7b0bd", "#1b212d", "#2f3848"],
  blocked: ["#8fb6ff", "#17203a", "#3a4a6b"], hot: ["#3fb67a", "#14211b", "#285a40"], idle: ["#a7b0bd", "#1b212d", "#2f3848"],
  safety: ["#e5604d", "#241817", "#5a2f29"], offline: ["#e5604d", "#1b212d", "#5a2f29"],
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let LOCALE;
const num = (v, d = 1) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n.toLocaleString(LOCALE, { maximumFractionDigits: d, minimumFractionDigits: 0 }) : "–";
};
const hhmm = (iso) => {
  if (!iso) return "";
  const dt = new Date(iso);
  return Number.isNaN(dt.getTime()) ? "" : dt.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });
};
const fill = (tpl, vars) => tpl.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ""));
const has = (v) => v !== null && v !== undefined;

class F1atbRouteurCard extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._sig = null;
    this._dur = this._dur || 60;
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
    return 3 + BLOCKS.filter((b) => this._config && this._config[b]).length * 3;
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
      if (e.platform === DOMAIN && e.device_id === this._deviceId && e.translation_key && !out[e.translation_key]) {
        out[e.translation_key] = e.entity_id;
      }
    }
    return out;
  }

  _st(key) {
    const id = this._ents[key];
    return id ? this._hass.states[id] : undefined;
  }

  _ok(st) {
    return st && !["unavailable", "unknown"].includes(st.state);
  }

  _render() {
    if (!this.shadowRoot || !this._hass) return;
    const t = this._t;
    LOCALE = this._hass.locale?.language || this._hass.language || undefined;
    this._ents = this._entities();
    const c = this._config || {};
    if (!this._deviceId) {
      this.shadowRoot.innerHTML = `${STYLE}<ha-card><div class="card muted">${esc(t.no_entity)}</div></ha-card>`;
      return;
    }
    const dev = (this._hass.devices || {})[this._deviceId] || {};
    const mode = this._st("operating_mode");
    const conn = this._st("connected");
    const fw = this._st("firmware");
    const sw = this._st("control_enabled");
    const status = this._st("status");
    const online = conn && conn.state === "on";
    const displayOnly = sw ? sw.state === "off" : false;
    const readOnly = fw?.attributes?.read_only;
    const modeVal = mode ? mode.state : "unknown";
    const info = status?.attributes || {};

    let html = `<ha-card><div class="card">`;
    html += `<div class="head">
      <div class="icon"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg></div>
      <div class="grow"><div class="title">${esc(dev.name_by_user || dev.name || "F1ATB")}</div>
      <div class="sub"><span class="dot ${online ? "on" : "off"}"></span>${online ? t.online : t.offline}${this._ok(fw) ? ` · ${t.firmware} ${esc(fw.state)}` : ""}</div></div>
      <div class="chip">${esc(displayOnly ? t.display : t.modes[modeVal] || modeVal)}</div></div>`;

    if (sw) {
      html += `<div class="seg" role="group" aria-label="${esc(t.pilot)}">
        <button data-sw="on" aria-pressed="${!displayOnly}" class="${displayOnly ? "" : "sel"}">${t.pilot}</button>
        <button data-sw="off" aria-pressed="${displayOnly}" class="${displayOnly ? "sel" : ""}">${t.display}</button></div>
        <div class="muted small">${displayOnly ? t.display_help : t.pilot_help}</div>`;
    }

    const key = !online ? "offline" : this._ok(status) ? status.state : "idle";
    html += this._status(t, key, info, displayOnly);
    if (c.show_tiles) html += this._tiles(t);
    if (c.show_controls && !displayOnly && !readOnly && online) html += this._controls(t, modeVal, info);
    if (c.show_planning) html += this._planning(t, dev);
    html += `<div class="foot"><a href="#" data-nav="/config/devices/device/${esc(this._deviceId)}">${t.settings}</a></div>`;
    html += `</div></ha-card>`;
    this.shadowRoot.innerHTML = STYLE + html;
    this._bind();
  }

  _status(t, key, a, displayOnly) {
    const tpl = t.st[key] || t.st.idle;
    const [color, bg, border] = COLORS[key] || COLORS.idle;
    const hasTemp = has(a.temperature);
    const vars = {
      power: num(a.power_w, 0),
      slotEnd: a.slot_end ? t.slot_until + a.slot_end : "",
      targetTxt: hasTemp ? `${num(a.target, 1)} °C` : t.hot_target,
      tempTxt: hasTemp ? fill(t.now_temp, { t: num(a.temperature, 1) }) : "",
      untilTxt: a.until ? t.until + hhmm(a.until) : "",
      controller: a.controller || "",
      reasonTxt: a.reason || "",
      tempOrThermo: hasTemp ? `${num(a.temperature, 1)} °C` : t.thermo,
    };
    if (key === "blocked" && !a.reason) vars.untilTxt = vars.untilTxt.replace(/^ · /, "");
    return `<div class="status" style="background:${bg};border-color:${border}">
      <span class="sdot" style="background:${color}"></span>
      <div><div class="stitle">${esc(fill(tpl[0], vars))}</div><div class="ssub">${esc(fill(tpl[1], vars))}</div>
      ${displayOnly ? `<div class="ssub">${esc(t.display_line)}</div>` : ""}</div></div>`;
  }

  _tiles(t) {
    const p = this._st("routed_power");
    const today = parseFloat(this._st("routed_energy_today")?.state);
    const grid = parseFloat(this._st("grid_energy_today")?.state);
    const solar = Number.isFinite(today) ? Math.max(0, today - (Number.isFinite(grid) ? grid : 0)) : NaN;
    return `<div class="tiles">
      <div class="tile"><div class="lbl">${t.to_ball}</div><div class="val">${num(p?.state, 0)} <span>W</span></div><div class="muted small">${p?.attributes?.measured ? t.measured : t.now}</div></div>
      <div class="tile"><div class="lbl">${t.solar_today}</div><div class="val">${num(solar, 1)} <span>kWh</span></div><div class="muted small">${t.free}</div></div>
      <div class="tile"><div class="lbl">${t.grid_today}</div><div class="val">${num(grid, 1)} <span>kWh</span></div><div class="muted small">${t.grid_sub}</div></div></div>`;
  }

  _controls(t, modeVal, a) {
    const locked = modeVal === "external";
    const mode = this._st("operating_mode");
    const userMode = mode?.attributes?.user_mode || modeVal;
    const btns = ["off", "solar", "solar_guarantee", "forced"].map((o) => {
      const sel = !locked && o === userMode;
      return `<button class="mbtn ${sel ? "sel" : ""}" data-mode="${o}" aria-pressed="${sel}" ${locked ? "disabled" : ""}>
        <span class="mlabel">${esc(t.modes[o])}</span><span class="msub">${esc(t.mode_sub[o])}</span></button>`;
    }).join("");
    let extra = "";
    if (!locked && userMode === "forced") {
      const end = a.until ? hhmm(a.until) : hhmm(new Date(Date.now() + this._dur * 60000).toISOString());
      const h = Math.floor(this._dur / 60), m = this._dur % 60;
      extra += `<div class="dur"><span class="muted">${t.during}</span>
        <div class="stepper"><button data-dur="-30" aria-label="${esc(t.less)}">−</button><b>${h} h ${String(m).padStart(2, "0")}</b><button data-dur="30" aria-label="${esc(t.more)}">+</button></div>
        <span class="muted">${t.until2} ${esc(end)}</span></div>`;
      const fo = this._st("force_opening");
      if (this._ok(fo)) {
        const v = parseInt(fo.state, 10);
        extra += `<div class="lab"><div class="row"><span>${t.fo}</span><b class="pct">${v} %</b></div>
          <input id="fo" type="range" min="5" max="100" step="1" value="${v}" aria-label="${esc(t.fo)}"></div>`;
      }
    }
    const statusKey = this._st("status")?.state;
    const running = !locked && (statusKey === "boost" || userMode === "forced");
    const targetTxt = has(a.temperature) ? `${num(a.target, 1)} °C` : t.hot_target;
    return `<div class="block"><div class="row"><div class="h">${t.what}</div>${locked ? `<span class="blue small">${t.piloted}</span>` : ""}</div>
      <div class="grid2">${btns}</div>${extra}
      ${locked ? `<div class="muted small">${esc(fill(t.locked_help, { controller: a.controller || "" }))}</div>` : ""}</div>
      <div class="block">
      <button class="heat" data-act="boost" ${locked ? "disabled" : ""}><span class="mlabel">${esc(fill(t.heat_now, { targetTxt }))}</span><span class="msub">${t.heat_sub}</span></button>
      ${running ? `<button class="stop" data-act="stop">${t.stop}</button>` : ""}</div>`;
  }

  _planning(t, dev) {
    const pl = this._st("planning");
    const slots = (pl && pl.attributes.slots) || [];
    const colors = { off: "#3b4556", on: "#e5604d", route: "#e3b341" };
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const seg = slots.map((s) => `<div style="width:${((s.end_min - s.start_min) / 1440) * 100}%;background:${colors[s.kind] || colors.off}"></div>`).join("");
    const describe = (s) => {
      if (s.kind === "on") {
        let txt = t.slot_on;
        if (has(s.on_opening) && s.on_opening < 100) txt += fill(t.at_pct, { p: s.on_opening });
        if (has(s.t_below)) txt += fill(t.if_below, { t: num(s.t_below, 1) });
        return txt;
      }
      if (s.kind === "route") {
        let txt = t.slot_route;
        if (has(s.t_below)) txt += fill(t.up_to, { t: num(s.t_below, 1) });
        return txt;
      }
      return t.slot_off;
    };
    const list = slots.filter((s) => s.kind !== "off").map((s) => `<div class="slot"><span class="sq" style="background:${colors[s.kind]}"></span>
      <span class="hrs">${esc(s.start)} – ${esc(s.end)}</span><span class="muted">${esc(describe(s))}${s.kind === "route" && has(s.threshold_w) ? ` <span class="faint">· ${esc(fill(t.threshold, { w: s.threshold_w }))}</span>` : ""}</span></div>`).join("");
    const url = dev.configuration_url ? `${dev.configuration_url.replace(/\/$/, "")}/Actions` : null;
    return `<div class="block"><div class="row"><div class="h">${t.planning}</div><div class="muted small">${t.set_in_router}</div></div>
      <div class="frise">${seg}<div class="nowline" style="left:${(nowMin / 1440) * 100}%"></div></div>
      <div class="ticks"><span>0 h</span><span>6 h</span><span>12 h</span><span>18 h</span><span>24 h</span></div>
      <div class="slots">${list}<div class="slot"><span class="sq" style="background:#3b4556"></span><span class="hrs">${t.rest}</span><span class="muted">${t.slot_off}</span></div></div>
      ${url ? `<div class="small"><a href="${esc(url)}" target="_blank" rel="noreferrer">${t.open_router}</a></div>` : ""}</div>`;
  }

  _call(domain, service, data) {
    return Promise.resolve(this._hass.callService(domain, service, data)).catch((err) => {
      const msg = err && (err.message || err.error) ? err.message || err.error : String(err);
      this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message: msg }, bubbles: true, composed: true }));
    });
  }

  _bind() {
    const root = this.shadowRoot;
    const dev = this._deviceId;
    root.querySelectorAll("[data-sw]").forEach((b) => b.addEventListener("click", () => {
      const id = this._ents.control_enabled;
      if (id) this._call("switch", b.dataset.sw === "on" ? "turn_on" : "turn_off", { entity_id: id });
    }));
    root.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
      const m = b.dataset.mode;
      if (m === "forced") this._call(DOMAIN, "set_mode", { device_id: dev, mode: "forced", duration: this._dur });
      else this._call(DOMAIN, "set_mode", { device_id: dev, mode: m });
    }));
    root.querySelectorAll("[data-dur]").forEach((b) => b.addEventListener("click", () => {
      this._dur = Math.max(30, Math.min(720, this._dur + parseInt(b.dataset.dur, 10)));
      this._call(DOMAIN, "set_mode", { device_id: dev, mode: "forced", duration: this._dur });
      this._sig = null;
      this._render();
    }));
    const fo = root.getElementById("fo");
    if (fo) {
      const pct = root.querySelector(".pct");
      fo.addEventListener("input", () => { if (pct) pct.textContent = `${fo.value} %`; });
      fo.addEventListener("change", () => {
        if (this._ents.force_opening) this._call("number", "set_value", { entity_id: this._ents.force_opening, value: parseInt(fo.value, 10) });
      });
    }
    root.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.act === "boost") this._call(DOMAIN, "boost", { device_id: dev });
      if (b.dataset.act === "stop") {
        this._call(DOMAIN, "cancel_boost", { device_id: dev });
        const mode = this._st("operating_mode");
        if (mode && mode.attributes.user_mode === "forced") {
          this._call(DOMAIN, "set_mode", { device_id: dev, mode: mode.attributes.prev_mode || "solar" });
        }
      }
    }));
    root.querySelectorAll("[data-nav]").forEach((a) => a.addEventListener("click", (ev) => {
      ev.preventDefault();
      history.pushState(null, "", a.dataset.nav);
      window.dispatchEvent(new CustomEvent("location-changed"));
    }));
  }
}

const STYLE = `<style>
  :host { --bg:#141922; --surf:#1b212d; --line:#2a3240; --ink:#e8ecf2; --mute:#a7b0bd; --accent:#4c8dff; }
  ha-card { background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 20px; overflow: hidden; }
  .card { padding: 18px; display: flex; flex-direction: column; gap: 14px; font-family: Inter, var(--paper-font-body1_-_font-family, system-ui), sans-serif; }
  .head { display: flex; align-items: center; gap: 12px; }
  .icon { width: 44px; height: 44px; border-radius: 12px; background: #1d2430; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .icon svg { width: 26px; height: 26px; fill: none; stroke: #e3b341; stroke-width: 1.8; stroke-linecap: round; }
  .grow { flex: 1; min-width: 0; }
  .title { font-size: 17px; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sub { font-size: 12.5px; color: var(--mute); display: flex; align-items: center; gap: 6px; }
  .dot { width: 8px; height: 8px; border-radius: 4px; display: inline-block; } .dot.on { background: #3fb67a; } .dot.off { background: #e5604d; }
  .chip { padding: 6px 12px; border-radius: 999px; background: #1d2a44; color: #b9d0ff; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .seg { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; background: #121720; border: 1px solid #2f3848; border-radius: 12px; padding: 4px; }
  .seg button { min-height: 44px; border-radius: 9px; border: 0; background: transparent; color: #c5ccd6; font-size: 13px; font-weight: 600; }
  .seg button.sel { background: var(--accent); color: #fff; }
  .status { display: flex; gap: 12px; align-items: flex-start; border-radius: 14px; padding: 14px; border: 1px solid; }
  .sdot { width: 12px; height: 12px; border-radius: 6px; margin-top: 5px; flex-shrink: 0; }
  .stitle { font-size: 17px; font-weight: 700; line-height: 1.3; } .ssub { font-size: 13px; color: #b3bccb; line-height: 1.45; margin-top: 3px; }
  .tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .tile, .block { background: var(--surf); border-radius: 14px; padding: 12px; }
  .block { display: flex; flex-direction: column; gap: 10px; padding: 14px; }
  .lbl { font-size: 11px; font-weight: 600; letter-spacing: .04em; color: var(--mute); }
  .val { font-size: 21px; font-weight: 700; margin-top: 4px; } .val span { font-size: 12px; color: var(--mute); }
  .h { font-size: 15px; font-weight: 600; }
  .row { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .muted { color: var(--mute); } .faint { color: #7d8796; } .blue { color: #8fb6ff; } .small { font-size: 12px; line-height: 1.45; }
  .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  button { font-family: inherit; cursor: pointer; }
  button:disabled { cursor: not-allowed; }
  .mbtn { min-height: 64px; padding: 10px 12px; text-align: left; border-radius: 12px; border: 1px solid #3a4454; background: transparent; color: var(--ink); }
  .mbtn.sel { border: 0; background: var(--accent); color: #fff; }
  .mbtn:disabled { color: #7d8796; }
  .mlabel { display: block; font-size: 14px; font-weight: 600; }
  .msub { display: block; font-size: 12px; margin-top: 3px; color: var(--mute); font-weight: 400; }
  .mbtn.sel .msub { color: #e3ecff; } .heat .msub { color: #ffe1dc; }
  .dur { display: flex; align-items: center; justify-content: space-between; background: #121720; border: 1px solid #2f3848; border-radius: 12px; padding: 8px 10px; font-size: 13px; }
  .stepper { display: flex; align-items: center; gap: 10px; }
  .stepper button { width: 44px; height: 44px; border-radius: 10px; border: 1px solid #3a4454; background: transparent; color: var(--ink); font-size: 20px; }
  .stepper b { min-width: 64px; text-align: center; font-size: 16px; }
  .lab { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--mute); }
  input[type=range] { width: 100%; accent-color: var(--accent); height: 28px; }
  .pct { color: var(--ink); }
  .heat { min-height: 64px; padding: 10px 14px; text-align: left; border-radius: 12px; border: 0; background: #e5604d; color: #fff; }
  .heat:disabled { background: #2a3240; color: #7d8796; } .heat:disabled .msub { color: #6f7886; }
  .stop { min-height: 48px; border-radius: 12px; border: 1px solid #e5604d; background: transparent; color: #ffb3a8; font-size: 14px; font-weight: 600; }
  .frise { position: relative; height: 30px; border-radius: 8px; overflow: hidden; display: flex; }
  .frise > div:not(.nowline) { height: 30px; border-right: 1px solid var(--bg); box-sizing: border-box; }
  .nowline { position: absolute; top: 0; bottom: 0; width: 2px; background: #fff; }
  .ticks { display: flex; justify-content: space-between; font-size: 11px; color: var(--mute); }
  .slots { display: flex; flex-direction: column; gap: 6px; }
  .slot { display: flex; gap: 10px; align-items: center; font-size: 13px; }
  .sq { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .hrs { width: 104px; color: #d5dbe4; flex-shrink: 0; }
  .foot { display: flex; justify-content: flex-end; font-size: 12px; }
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
      ? { entity: "Routeur (sélecteur de mode)", show_tiles: "Tuiles (puissance, énergies du jour)", show_controls: "Commandes (mode, marche forcée, chauffer maintenant)", show_planning: "Planning du routeur" }
      : { entity: "Router (mode selector)", show_tiles: "Tiles (power, today's energy)", show_controls: "Controls (mode, forced on, heat now)", show_planning: "Router schedule" };
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
    description: "Routeur solaire F1ATB : état, mode, marche forcée, planning / F1ATB solar router",
    preview: false,
  });
}
console.info(`%c F1ATB-ROUTEUR-CARD %c v${CARD_VERSION} `, "background:#e3b341;color:#141922;font-weight:700", "background:#141922;color:#e3b341");
