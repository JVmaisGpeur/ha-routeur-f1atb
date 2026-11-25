# Routeur F1ATB pour Home Assistant

🇬🇧 [English version](README.en.md)

Intégration Home Assistant pour piloter en local un **routeur solaire F1ATB** (RMS sur ESP32, firmware officiel non modifié). Elle fonctionne seule, ou sous les ordres d'un pilote externe (automatisation ou autre intégration) grâce à une interface de prise de main générique.

- Lecture des mesures, du planning et de l'état des sorties du routeur.
- Modes : **Arrêt**, **Solaire seul**, **Solaire + garantie** (rattrapage en heures creuses si le soleil n'a pas suffi), **Marche forcée**.
- « Ballon chaud » avec sonde, par détection de la coupure du thermostat, ou par énergie de chauffe.
- Puissance du chauffe-eau déclarée, mesurée par un compteur dédié, ou calibrée par le compteur de surplus.
- Pilotage externe qui expire tout seul au bout de 30 min sans renouvellement, avec la raison affichée sur la carte.
- Interrupteur **Piloter le routeur / Affichage seulement** : Home Assistant peut se contenter d'afficher les infos du routeur sans rien lui envoyer.
- Carte Lovelace incluse, bilingue français / anglais.

> Projet indépendant, non affilié à F1ATB. Merci à F1ATB pour le routeur, et à [WillSpecIm/Integration-f1atb](https://github.com/WillSpecIm/Integration-f1atb) pour la documentation de l'API.

## Compatibilité

| Firmware | Fonctions |
| --- | --- |
| 17.xx (vérifié en 17.30) | Toutes |
| 16.xx (vérifié en 16.10) | Toutes ; la marche forcée est toujours à 100 % (pas d'« ouverture si forcée ») ; chaque appui On ajoute 30 min, Off arrête tout, un appui On annule un arrêt forcé |
| Autres versions | Lecture seule (mesures, planning) et notification de réparation : ouvrez un ticket avec les diagnostics |

La version est détectée automatiquement. Home Assistant 2024.11 ou plus récent.

## Ce que l'intégration envoie au routeur

Pour le pilotage, uniquement des **forçages temporaires de 30 min**, décomptés par le routeur lui-même (`/ForceAction` en 17.xx, boutons On/Off de l'accueil en 16.xx). Le pilotage **n'écrit jamais** dans la configuration du routeur : horaires, seuil Pw, conditions et forme d'onde restent vos réglages, faits dans l'interface du routeur.

Seule exception, en 17.xx : l'**ouverture en marche forcée** (« Ouverture si forcée ») se règle depuis Home Assistant. Elle est enregistrée dans le routeur uniquement quand vous la changez vous-même, jamais par le pilotage automatique. Si Home Assistant s'arrête, le routeur reprend seul son planning au plus tard 30 min après.

Le routeur ne mesure pas la puissance de ses sorties : il mesure seulement le point de raccordement au réseau (Shelly, Linky, pince…). Sans compteur dédié au chauffe-eau, la puissance routée est donc **estimée** (ouverture × puissance du chauffe-eau).

## Installation

1. HACS → menu ⋮ → **Dépôts personnalisés** → `https://github.com/JVmaisGpeur/ha-routeur-f1atb`, catégorie **Intégration**.
2. Installez **Routeur F1ATB**, puis redémarrez Home Assistant.
3. **Paramètres → Appareils et services → Ajouter une intégration → Routeur F1ATB**, puis :
   - **Rechercher sur le réseau** : l'intégration parcourt votre réseau local (jusqu'à 1024 adresses) et liste les routeurs F1ATB trouvés. Cochez ceux à ajouter : le premier se configure tout de suite, les autres apparaissent dans **Découverts** pour être confirmés un par un ;
   - **Saisir l'adresse IP** si la recherche ne trouve rien.

   Les routeurs vus par le DHCP (nom réseau `RMS-ESP32-…`) et ceux que connaît un routeur déjà ajouté sont aussi proposés dans **Découverts**. Chacun doit être confirmé ; « Ignorer » : il n'est plus proposé.

La recherche ne lit que la page d'accueil de chaque adresse : elle n'appelle aucune autre page et n'envoie aucune commande.

### Configuration

Une question par écran, et seulement celles qui vous concernent :

1. **Sortie du chauffe-eau** : posée seulement si le routeur a plusieurs sorties actives.
2. **Température de l'eau** : sonde du routeur (choisie d'office s'il n'y en a qu'une), capteur Home Assistant, ou **Pas de sonde**.
3. Sans sonde seulement : **quand l'eau est-elle chaude ?** Coupure du thermostat (le plus simple) ou après une énergie de chauffe. La consigne et la température de sécurité ne sont alors pas demandées.
4. **Puissance du chauffe-eau** : plaque du ballon, compteur dédié, ou calibration après l'installation.
5. **Heures creuses** : début et fin (la garantie vise la fin des heures creuses), et la consigne s'il y a une sonde. Si votre planning contient déjà une plage ON, l'intégration démarre en « Solaire seul » pour ne pas chauffer deux fois.

**Options**, en trois rubriques : *Chauffe-eau* (mêmes questions), *Heures creuses et consigne* (hystérésis, heure limite, entité « heures creuses » facultative), *Avancé* (pilotage externe, durée maximale d'une marche forcée, capteur réseau, intervalle, format du firmware, température de sécurité).

### Réglages conseillés dans le routeur

- Une **plage ROUTAGE large**, par exemple de 8 h à 20 h : l'intégration (ou un pilote) peut toujours couper une plage par un arrêt forcé, mais ne peut pas en créer.
- Avec des batteries qui régulent le point de raccordement : un **seuil Pw au moins 20 W plus bas que la cible des batteries** (ex. −20 à −50 W pour une cible à 0 W), pour que les batteries prennent le surplus en premier.

## Piloter ou afficher seulement

L'interrupteur **Piloter le routeur** (aussi sur la carte) choisit le rôle de Home Assistant :

- **en marche** (par défaut) : l'intégration et les pilotes externes peuvent commander le routeur ;
- **à l'arrêt, « Affichage seulement »** : l'intégration rend la main (elle annule une fois son propre forçage en cours), puis n'envoie plus rien. Mesures, planning et état restent affichés. Les services de commande sont refusés avec un message clair, et un pilote externe qui avait la main la perd.

Le Chef d'orchestre énergie (ou tout autre pilote) lit cet interrupteur, clé `control_enabled`, pour savoir s'il peut commander le routeur.

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
| `sensor` État | Ce que fait le chauffe-eau en une phrase : `solar`, `waiting_surplus`, `on_slot`, `boost`, `forced`, `off`, `blocked`, `hot`, `idle`, `safety` (attributs : puissance, température, consigne, pilote, raison, fin de plage…) |
| `switch` Piloter le routeur | En marche : pilotage ; à l'arrêt : affichage seulement |
| `select` Mode | Mode de fonctionnement (attributs `user_mode`, `controller`, `reason`) |
| `sensor` Puissance routée | Mesurée (compteur dédié) ou estimée |
| `sensor` Énergie routée aujourd'hui / totale | Totale compatible avec le tableau Énergie |
| `sensor` Énergie réseau (rattrapage) aujourd'hui | Énergie chauffée pendant une marche forcée ou une plage ON |
| `sensor` Température du ballon | Si une sonde est configurée |
| `sensor` Ouverture, Forçage restant, Plage en cours | État de la sortie et planning (attribut `slots`) |
| `sensor` Pilotage externe | Nom du pilote (attributs `controller`, `controlled_keys`, `expires_at`, `reason`) |
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
    reason: "Batteries prioritaires"
# Bloquer le routeur (arrêts forcés de 30 min renouvelés)
- action: f1atb_routeur.set_mode
  data:
    device_id: !input routeur
    mode: "off"
    controller: "Mon pilote"
    reason: "Batteries prioritaires"
# Rendre la main
- action: f1atb_routeur.set_external_control
  data:
    device_id: !input routeur
    active: false
    controller: "Mon pilote"
```

La `reason` (facultative) est affichée sur la carte : « Bloqué par Mon pilote – Batteries prioritaires ».

Un appel venant de l'utilisateur sur un réglage pris en main est refusé, sauf avec `override: true`, qui met fin au pilotage externe. Tous les services de commande sont refusés en « Affichage seulement ».

## Carte

La carte `custom:f1atb-routeur-card` est chargée automatiquement. Ajoutez-la depuis le tableau de bord (« Routeur F1ATB »). Elle montre toujours le nom du routeur, l'interrupteur **Piloter / Affichage seulement** et une phrase qui dit ce que fait le chauffe-eau (« Chauffe avec le surplus solaire – 1 240 W envoyés au ballon jusqu'à 20:00 », « Bloqué par Chef d'orchestre énergie – Batteries prioritaires »…). Trois blocs facultatifs s'activent dans l'éditeur :

| Clé | Bloc |
| --- | --- |
| `show_tiles` | Puissance vers le ballon, énergie solaire et réseau du jour |
| `show_controls` | « Que doit faire le chauffe-eau ? » (4 modes expliqués), durée et ouverture de la marche forcée, « Chauffer maintenant », « Arrêter et revenir au planning » |
| `show_planning` | Planning du routeur en clair (« Chauffe avec le surplus solaire jusqu'à 60 °C ») |

```yaml
type: custom:f1atb-routeur-card
entity: select.ecs_f1atb_mode
show_tiles: true
show_controls: true
show_planning: true
```

Les commandes sont masquées en « Affichage seulement », hors ligne ou en lecture seule, et verrouillées quand un pilote externe a la main. Les réglages de l'installation (sonde, puissance…) sont dans **Réglages de l'appareil**, en bas de la carte.

## Limites connues (v1.1.0)

- Le seuil Pw, les horaires et la forme d'onde se lisent mais ne se modifient pas depuis Home Assistant (réglages du routeur). La forme d'onde n'apparaît pas sur la carte.
- Seule la sortie qui alimente le chauffe-eau est gérée ; les autres sorties du même routeur n'apparaissent pas.
- La marche forcée se fait à l'« ouverture si forcée » (réglable en 17.xx) ou à 100 % (16.xx) ; pas de marche forcée à une puissance donnée en W.
- Sans sonde ni compteur dédié, la coupure du thermostat est déduite d'un saut d'injection au compteur : méthode approximative (un nuage qui passe peut la tromper).
- Si des batteries compensent la consommation pendant la calibration, l'écart mesuré est faussé : mettez-les à l'arrêt quelques secondes, ou déclarez la puissance.
- Ne laissez pas le routeur accessible depuis Internet : son API n'a pas d'authentification et sa configuration contient vos mots de passe en clair. L'intégration ne les stocke ni ne les journalise, et les masque dans les diagnostics.

## Licence

MIT – © 2026 JVmaisGpeur
