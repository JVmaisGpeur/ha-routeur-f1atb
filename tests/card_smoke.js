// Test rapide de rendu de la carte v1.1.0 sans navigateur (node tests/card_smoke.js)
class FakeRoot { constructor() { this.innerHTML = ""; } querySelectorAll() { return []; } querySelector() { return null; } getElementById() { return null; } }
global.HTMLElement = class { attachShadow() { this.shadowRoot = new FakeRoot(); return this.shadowRoot; } appendChild() {} dispatchEvent() {} };
const defs = {};
global.customElements = { get: (n) => defs[n], define: (n, c) => { defs[n] = c; } };
global.window = {};
global.document = { createElement: () => ({}) };
global.CustomEvent = class {};
require("../custom_components/f1atb_routeur/f1atb-routeur-card.js");
const Card = defs["f1atb-routeur-card"];
const fail = (m) => { console.error(m); process.exit(1); };
const ent = (id, key) => ({ entity_id: id, platform: "f1atb_routeur", device_id: "dev1", translation_key: key });
const keys = ["operating_mode", "connected", "firmware", "status", "control_enabled", "external_control", "routed_power", "routed_energy_today",
  "grid_energy_today", "water_temperature", "target_temperature", "planning", "force_opening"];
const entities = {}; const states = {};
for (const k of keys) { const id = `x.ecs_${k}`; entities[id] = ent(id, k); states[id] = { state: "0", attributes: {}, last_updated: "t" }; }
states["x.ecs_operating_mode"] = { state: "solar_guarantee", attributes: { user_mode: "solar_guarantee", prev_mode: "solar" } };
states["x.ecs_connected"].state = "on";
states["x.ecs_firmware"].state = "17.30";
states["x.ecs_control_enabled"].state = "on";
states["x.ecs_status"] = { state: "solar", attributes: { power_w: 1240, temperature: 44.1, target: 55, slot_end: "20:00" } };
states["x.ecs_routed_power"].state = "1240";
states["x.ecs_routed_energy_today"].state = "1.8";
states["x.ecs_grid_energy_today"].state = "0.4";
states["x.ecs_planning"] = { state: "route", attributes: { force_opening: 100, slots: [
  { start: "0:00", end: "4:00", start_min: 0, end_min: 240, kind: "off", threshold_w: null, on_opening: null, t_below: null },
  { start: "4:00", end: "5:59", start_min: 240, end_min: 359, kind: "on", threshold_w: null, on_opening: 100, t_below: 50 },
  { start: "5:59", end: "24:00", start_min: 359, end_min: 1440, kind: "route", threshold_w: -20, on_opening: null, t_below: 60 }] } };
states["x.ecs_force_opening"].state = "80";
const hass = { language: "fr", entities, states, devices: { dev1: { name: "ECS_F1ATB", configuration_url: "http://192.168.1.201" } }, callService() {} };
const render = (cfg) => { const c = new Card(); c.setConfig({ entity: "x.ecs_operating_mode", ...cfg }); c.hass = hass; return [c, norm(c.shadowRoot.innerHTML)]; };
function norm(h) { return h.replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/[\u202f\u00a0]/g, " "); }
const check = (html, must, label) => { for (const m of must) if (!html.includes(m)) fail(`${label} – absent : ${m}`); };
const none = (html, bad, label) => { for (const m of bad) if (html.includes(m)) fail(`${label} – ne devrait pas apparaître : ${m}`); };

// 1. Carte minimale : en-tête, interrupteur, phrase d'état, rien d'autre.
let [card, html] = render({});
check(html, ["ECS_F1ATB", "firmware 17.30", "Piloter le routeur", "Affichage seulement", "Chauffe avec le surplus solaire", "1 240 W envoyés au ballon jusqu'à 20:00", "Réglages de l'appareil"], "minimale");
none(html, ["Que doit faire", "Planning du routeur", "VERS LE BALLON", "Ballon d'eau chaude"], "minimale");

// 2. Tous les blocs.
[card, html] = render({ show_tiles: true, show_controls: true, show_planning: true });
check(html, ["VERS LE BALLON", "1,4", "0,4", "Que doit faire le chauffe-eau ?", "Solaire + garantie", "Chauffer maintenant jusqu'à 55 °C",
  "Planning du routeur", "Chauffe sur le réseau si l'eau est sous 50 °C", "Chauffe avec le surplus solaire jusqu'à 60 °C", "seuil -20 W", "Ouvrir le routeur"], "complète");
none(html, ["Ouverture en marche forcée", "Arrêter et revenir"], "complète (mode solaire)");

// 3. Marche forcée : durée, curseur 17.xx et bouton d'arrêt.
states["x.ecs_operating_mode"] = { state: "forced", attributes: { user_mode: "forced", prev_mode: "solar_guarantee" } };
states["x.ecs_status"] = { state: "forced", attributes: { power_w: 2000, until: new Date(Date.now() + 3600e3).toISOString() } };
[card, html] = render({ show_controls: true });
check(html, ["Marche forcée", "Pendant", "1 h 00", "Ouverture en marche forcée", "80 %", "Arrêter et revenir au planning du routeur"], "forcée");

// 4. Piloté par le Chef d'orchestre : boutons verrouillés + raison.
states["x.ecs_operating_mode"] = { state: "external", attributes: { user_mode: "solar_guarantee", controller: "Chef d'orchestre énergie" } };
states["x.ecs_status"] = { state: "blocked", attributes: { controller: "Chef d'orchestre énergie", reason: "Batteries prioritaires" } };
[card, html] = render({ show_controls: true });
check(html, ["Bloqué par Chef d'orchestre énergie", "Batteries prioritaires", "piloté", "Chef d'orchestre énergie a la main", "disabled"], "pilotée");

// 5. Sans sonde : pas de température.
states["x.ecs_status"] = { state: "hot", attributes: {} };
states["x.ecs_operating_mode"] = { state: "solar", attributes: { user_mode: "solar" } };
[card, html] = render({ show_controls: true });
check(html, ["Ballon chaud, ne chauffe plus", "Le thermostat a coupé", "Chauffer maintenant jusqu'à ballon chaud"], "sans sonde");

// 6. Affichage seulement : pas de commandes.
states["x.ecs_control_enabled"].state = "off";
[card, html] = render({ show_controls: true });
check(html, ["Affichage seulement : aucune commande n'est envoyée."], "affichage seul");
none(html, ["Que doit faire"], "affichage seul");
states["x.ecs_control_enabled"].state = "on";

// 7. Hors ligne.
states["x.ecs_connected"].state = "off";
[card, html] = render({ show_controls: true });
check(html, ["Routeur hors ligne", "Hors ligne"], "hors ligne");
none(html, ["Que doit faire"], "hors ligne");
states["x.ecs_connected"].state = "on";

// 8. Anglais.
hass.language = "en";
states["x.ecs_status"] = { state: "waiting_surplus", attributes: { slot_end: "20:00" } };
[card, html] = render({ show_tiles: true, show_controls: true, show_planning: true });
check(html, ["Waiting for solar surplus", "Control the router", "What should the water heater do?", "Router schedule", "Device settings"], "anglais");
if (/sinus|forme d'onde/i.test(html)) fail("forme d'onde encore affichée");
console.log("carte ok : 8 scénarios");
