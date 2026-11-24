// Test rapide de rendu de la carte sans navigateur (node tests/card_smoke.js)
class FakeRoot { constructor() { this.innerHTML = ""; } querySelectorAll() { return []; } getElementById() { return null; } }
global.HTMLElement = class { attachShadow() { this.shadowRoot = new FakeRoot(); return this.shadowRoot; } appendChild() {} dispatchEvent() {} };
const defs = {};
global.customElements = { get: (n) => defs[n], define: (n, c) => { defs[n] = c; } };
global.window = {};
global.document = { createElement: () => ({}) };
global.CustomEvent = class {};
require("../custom_components/f1atb_routeur/f1atb-routeur-card.js");
const Card = defs["f1atb-routeur-card"];
const ent = (id, key) => ({ entity_id: id, platform: "f1atb_routeur", device_id: "dev1", translation_key: key });
const keys = ["operating_mode", "connected", "firmware", "external_control", "routed_power", "routed_energy_today", "grid_energy_today",
  "water_temperature", "target_temperature", "target_reached", "thermostat_open", "boost_active", "water_heater_power", "planning", "force_remaining", "opening", "calibrate", "force_opening"];
const entities = {}; const states = {};
for (const k of keys) { const id = `x.ecs_${k}`; entities[id] = ent(id, k); states[id] = { state: "0", attributes: {}, last_updated: "t" }; }
states["x.ecs_operating_mode"].state = "solar_guarantee";
states["x.ecs_connected"].state = "on";
states["x.ecs_firmware"].state = "17.30";
states["x.ecs_external_control"] = { state: "Chef d'orchestre énergie", attributes: { controlled_keys: ["mode"], expires_at: new Date().toISOString() } };
states["x.ecs_water_temperature"].state = "44.1";
states["x.ecs_target_temperature"].state = "55";
states["x.ecs_routed_energy_today"].state = "1.8";
states["x.ecs_planning"] = { state: "off", attributes: { current: { kind: "off" }, force_opening: 100, slots: [
  { start: "0:00", end: "4:00", start_min: 0, end_min: 240, kind: "off", threshold_w: null, on_opening: null, t_below: null, t_above: null },
  { start: "4:00", end: "5:59", start_min: 240, end_min: 359, kind: "on", threshold_w: null, on_opening: 100, t_below: 50, t_above: null },
  { start: "5:59", end: "24:00", start_min: 359, end_min: 1440, kind: "route", threshold_w: -20, on_opening: null, t_below: 60, t_above: null }] } };
states["x.ecs_opening"].attributes = { action: "Chauffe-eau", is_triac: true, on_off: false };
states["x.ecs_force_opening"].state = "80";
const hass = { language: "fr", entities, states, devices: { dev1: { name: "ECS_F1ATB", configuration_url: "http://192.168.1.201" } }, callService() {} };
const c = new Card();
c.setConfig({ entity: "x.ecs_operating_mode", show_tiles: true, show_water: true, show_planning: true, show_mode: true, show_forcing: true, show_output: true });
c.hass = hass;
const html = c.shadowRoot.innerHTML;
const must = ["Ouverture en marche forcée", "80 %", "Chauffe-eau · Triac", "ECS_F1ATB", "Piloté par Chef", "44,1 °C", "Planning du routeur", "seuil -20 W", "T ≤ 50 °C", "Marche forcée", "Calibrer", "1,8"];
for (const m of must) if (!html.includes(m)) { console.error("absent :", m); process.exit(1); }
if (/sinus|forme d'onde/i.test(html)) { console.error("forme d'onde encore affichée"); process.exit(1); }
console.log("rendu ok,", html.length, "caractères");
hass.language = "en"; c._sig = null; c.hass = hass;
if (!c.shadowRoot.innerHTML.includes("Controlled by")) { console.error("anglais absent"); process.exit(1); }
console.log("anglais ok");
