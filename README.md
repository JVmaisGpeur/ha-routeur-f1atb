# Routeur F1ATB pour Home Assistant

🇬🇧 [English version](README.en.md)

Intégration Home Assistant pour piloter en local un **routeur solaire F1ATB** (RMS sur ESP32, firmware officiel non modifié). Elle fonctionne seule, ou sous les ordres d'un pilote externe (automatisation ou autre intégration) grâce à une interface de prise de main générique.

- Lecture des mesures, du planning et de l'état des sorties du routeur.
- Modes : **Arrêt**, **Solaire seul**, **Solaire + garantie** (rattrapage en heures creuses si le soleil n'a pas suffi), **Marche forcée**.
- « Ballon chaud » avec sonde, par détection de la coupure du thermostat, ou par énergie de chauffe.
- Puissance du chauffe-eau déclarée, mesurée par un compteur dédié, ou calibrée par le compteur de surplus.
- Pilotage externe qui expire tout seul au bout de 30 min sans renouvellement.
- Carte Lovelace incluse, bilingue français / anglais.

> Projet indépendant, non affilié à F1ATB. Merci à F1ATB pour le routeur, et à [WillSpecIm/Integration-f1atb](https://github.com/WillSpecIm/Integration-f1atb) pour la documentation de l'API.

## Compatibilité

| Firmware | Fonctions |
| --- | --- |
| 17.xx (vérifié en 17.30) | Toutes |
| 16.xx (vérifié en 16.10) | Toutes ; la marche forcée est toujours à 100 % (pas d'« ouverture si forcée ») ; un arrêt forcé ne peut pas être annulé et expire seul en 30 min au plus |
| Autres versions | Lecture seule (mesures, planning) et notification de réparation : ouvrez un ticket avec les diagnostics |

La version est détectée automatiquement. Home Assistant 2024.11 ou plus récent.

## Ce que l'intégration envoie au routeur

Pour le pilotage, uniquement des **forçages temporaires de 30 min**, décomptés par le routeur lui-même (`/ForceAction` en 17.xx, boutons On/Off de l'accueil en 16.xx). Le pilotage **n'écrit jamais** dans la configuration du routeur : horaires, seuil Pw, conditions et forme d'onde restent vos réglages, faits dans l'interface du routeur.

Seule exception, en 17.xx : l'**ouverture en marche forcée** (« Ouverture si forcée ») se règle depuis Home Assistant. Elle est enregistrée dans le routeur uniquement quand vous la changez vous-même, jamais par le pilotage automatique. Si Home Assistant s'arrête, le routeur reprend seul son planning au plus tard 30 min après.

Le routeur ne mesure pas la puissance de ses sorties : il mesure seulement le point de raccordement au réseau (Shelly, Linky, pince…). Sans compteur dédié au chauffe-eau, la puissance routée est donc **estimée** (ouverture × puissance du chauffe-eau).

## Installation

1. HACS → menu ⋮ → **Dépôts personnalisés** → `https://github.com/JVmaisGpeur/ha-routeur-f1atb`, catégorie **Intégration**.
2. Installez **Routeur F1ATB**, puis redémarrez Home Assistant.
3. **Paramètres → Appareils et services** :
   - les routeurs détectés sur le réseau (nom réseau `RMS-ESP32-…`) apparaissent dans **Découverts** ;
   - après l'ajout d'un premier routeur, ceux qu'il connaît (déclarés dans sa configuration) sont aussi proposés ;
   - sinon **Ajouter une intégration → Routeur F1ATB** et saisissez l'adresse IP.

   Chaque routeur détecté doit être confirmé (nom, adresse, firmware, sorties). « Ignorer » : il n'est plus proposé.

Un routeur dont l'adresse IP fixe est réglée dans le routeur lui-même (sans DHCP) n'est pas vu par la découverte : ajoutez-le par son adresse.

### Configuration

**Chauffe-eau** : sortie qui l'alimente (triac ou relais), source de température (sonde du routeur, capteur Home Assistant ou aucune), source de puissance (déclarée, compteur dédié, calibration) et méthode « ballon chaud » (température, coupure du thermostat, énergie de chauffe).

**Fonctionnement autonome** : consigne (55 °C par défaut), heures creuses (entité facultative, ou horaires), heure limite de la garantie. Si votre planning contient déjà une plage ON (rattrapage fait par le routeur), l'intégration démarre en « Solaire seul » pour ne pas chauffer deux fois.

**Options** : hystérésis, température de sécurité (65 °C, coupe tout forçage), durée maximale d'une marche forcée manuelle, autorisation du pilotage externe, capteur de puissance réseau facultatif, intervalle d'interrogation, format du firmware (secours).

### Réglages conseillés dans le routeur

- Une **plage ROUTAGE large**, par exemple de 8 h à 20 h : l'intégration (ou un pilote) peut toujours couper une plage par un arrêt forcé, mais ne peut pas en créer.
- Avec des batteries qui régulent le point de raccordement : un **seuil Pw au moins 20 W plus bas que la cible des batteries** (ex. −20 à −50 W pour une cible à 0 W), pour que les batteries prennent le surplus en premier.

## Modes

| Mode | Comportement |
| --- | --- |
| Arrêt | Arrêts forcés de 30 min renouvelés : le chauffe-eau reste coupé |
| Solaire seul | Le routeur suit son planning, l'intégration n'envoie rien |
| Solaire + garantie | Planning du routeur ; puis, entre le début des heures creuses et l'heure limite, marche forcée tant que le ballon n'est pas chaud. Événement `f1atb_routeur_target_missed` si la consigne n'est pas atteinte à l'heure limite |
| Marche forcée | Marche forcée pendant la durée choisie (12 h au plus), puis retour au mode précédent |
| Piloté | Choisi automatiquement quand un pilote externe a la main sur le mode |

Priorités : sécurité thermique → action de l'utilisateur avec `override` → pilote externe → règles autonomes.

## Entités

| Entité | Rôle |
| --- | --- |
| `select` Mode | Mode de fonctionnement |
| `sensor` Puissance routée | Mesurée (compteur dédié) ou estimée |
| `sensor` Énergie routée aujourd'hui / totale | Totale compatible avec le tableau Énergie |
| `sensor` Énergie réseau (rattrapage) aujourd'hui | Énergie chauffée pendant une marche forcée ou une plage ON |
| `sensor` Température du ballon | Si une sonde est configurée |
| `sensor` Ouverture, Forçage restant, Plage en cours | État de la sortie et planning (attribut `slots`) |
| `sensor` Pilotage externe | Nom du pilote (attributs `controller`, `controlled_keys`, `expires_at`) |
| `number` Consigne, Puissance du chauffe-eau | Réglages |
| `number` Ouverture si forcée (17.xx) | Ouverture pendant une marche forcée, enregistrée dans le routeur quand vous la changez |
| `binary_sensor` Connecté, Ballon chaud, Rattrapage en cours, Thermostat coupé | |
| `button` Calibrer la puissance | Marche forcée de quelques secondes et mesure de l'écart au compteur |

Diagnostic : tarif du jour, firmware, signal Wi-Fi, durée de fonctionnement, autres sondes.

## Services

| Service | Rôle |
| --- | --- |
| `f1atb_routeur.set_mode` | Changer de mode (`duration` pour la marche forcée) |
| `f1atb_routeur.boost` / `cancel_boost` | Rattrapage ponctuel (durée, énergie ou température) |
| `f1atb_routeur.set_target_temperature` | Consigne |
| `f1atb_routeur.calibrate` | Calibration de la puissance |
| `f1atb_routeur.set_external_control` | Prise de main par un pilote externe |

### Pilotage externe

Un pilote (automatisation, autre intégration) prend la main sur certains réglages (`mode`, `boost`, `target_temperature`) et doit la **renouveler avant 30 min** ; sinon elle expire, l'événement `f1atb_routeur_external_control_expired` est émis et le routeur revient à son mode. Les réglages non pris en main restent gérés par les règles autonomes.

```yaml
# Prendre la main (à renouveler toutes les 10 à 20 min)
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input routeur
    active: true
    controller: "Mon pilote"
    controlled_keys: [mode]
# Bloquer le routeur (arrêts forcés de 30 min renouvelés)
- action: f1atb_routeur.set_mode
  data:
    device_id: !input routeur
    mode: "off"
    controller: "Mon pilote"
# Rendre la main
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input routeur
    active: false
    controller: "Mon pilote"
```

Un appel venant de l'utilisateur sur un réglage pris en main est refusé, sauf avec `override: true`, qui met fin au pilotage externe.

## Carte

La carte `custom:f1atb-routeur-card` est chargée automatiquement. Ajoutez-la depuis le tableau de bord (« Routeur F1ATB ») et activez ses blocs dans l'éditeur (tous masqués par défaut) :

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

## Limites connues (v1.0.0)

- Le seuil Pw, les horaires et la forme d'onde se lisent mais ne se modifient pas depuis Home Assistant (réglages du routeur). La forme d'onde n'apparaît pas sur la carte.
- Seule la sortie qui alimente le chauffe-eau est gérée ; les autres sorties du même routeur n'apparaissent pas.
- La marche forcée se fait à l'« ouverture si forcée » (réglable en 17.xx) ou à 100 % (16.xx) ; pas de marche forcée à une puissance donnée en W.
- Sans sonde ni compteur dédié, la coupure du thermostat est déduite d'un saut d'injection au compteur : méthode approximative (un nuage qui passe peut la tromper).
- Si des batteries compensent la consommation pendant la calibration, l'écart mesuré est faussé : mettez-les à l'arrêt quelques secondes, ou déclarez la puissance.
- Ne laissez pas le routeur accessible depuis Internet : son API n'a pas d'authentification et sa configuration contient vos mots de passe en clair. L'intégration ne les stocke ni ne les journalise, et les masque dans les diagnostics.

## Licence

MIT – © 2026 JVmaisGpeur
