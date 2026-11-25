# Changelog

## 1.1.1 – recherche réseau / network search
- **Correction** : après la recherche, l'écran de choix des routeurs trouvés était refusé par Home Assistant (« 400 Bad Request »), de même que les écrans « sortie » et « sonde » quand le routeur en a plusieurs. / Fix: the router list, output and probe screens were rejected by Home Assistant (400 Bad Request).
- **Recherche réseau corrigée** : un routeur est maintenant reconnu à sa page d'état `/ajax_dataESP32` (16.xx et 17.xx) et non plus au texte de sa page d'accueil, avec des délais adaptés à un ESP32 lent à répondre. / Routers are now recognised by their `/ajax_dataESP32` status page, with longer timeouts.
- Si aucun nouveau routeur n'est trouvé, l'écran de saisie affiche le compte rendu de la recherche (réseau parcouru, serveurs web, routeurs déjà ajoutés). / Search report shown when no new router is found.

## 1.1.0 – retours d'essai / test feedback
- **Recherche sur le réseau** à l'installation : liste des routeurs F1ATB trouvés, choix de ceux à ajouter (les suivants passent par « Découverts »), saisie de l'adresse en secours. / Network search during setup, with a multi-select of the routers found.
- **Configuration simplifiée** : une question par écran, seulement celles utiles (sortie demandée seulement s'il y en a plusieurs, sonde unique choisie d'office, consigne masquée sans sonde, heure limite = fin des heures creuses). Options en trois rubriques. / Simplified setup, one question per screen; options split in three sections.
- **Interrupteur « Piloter le routeur »** (`control_enabled`) : à l'arrêt, affichage seulement ; l'intégration annule une fois son forçage puis n'envoie plus rien, les services de commande sont refusés. / Display-only switch.
- **Capteur « État »** : ce que fait le chauffe-eau (solaire, attente de surplus, plage ON, rattrapage, marche forcée, arrêt, bloqué par un pilote, ballon chaud, sécurité…) avec ses détails en attributs. / New status sensor.
- **Raison** (`reason`) facultative dans `set_external_control` et `set_mode`, affichée sur la carte. / Optional reason shown on the card.
- **Nouvelle carte** : phrase d'état claire, interrupteur Piloter / Affichage seulement, 4 modes expliqués, « Chauffer maintenant », « Arrêter et revenir au planning », planning en clair, lien vers les réglages ; blocs `show_tiles`, `show_controls`, `show_planning`. Le bloc « Ballon d'eau chaude » est supprimé. / Redesigned card.
- 16.xx : un arrêt forcé est maintenant annulé (un appui On l'annule). / 16.xx forced-off can now be cancelled.
- Icône de l'intégration (`brand/`) pour la validation HACS. / Integration icon for HACS validation.

## 1.0.0 – première version / first release
- Détection automatique du firmware (17.xx JSON, 16.xx texte) ; lecture seule pour une version non vérifiée.
- Découverte DHCP (`RMS-ESP32-*`) et routeurs connus d'un routeur déjà ajouté, avec confirmation.
- Modes Arrêt, Solaire seul, Solaire + garantie, Marche forcée ; pilotage externe qui expire après 30 min.
- Forçages temporaires de 30 min uniquement, aucune écriture dans la configuration du routeur.
- Sonde, coupure du thermostat ou énergie pour « ballon chaud » ; puissance déclarée, compteur dédié ou calibration.
- « Ouverture si forcée » réglable depuis la carte en 17.xx (écrite seulement à la demande de l'utilisateur).
- Carte Lovelace bilingue (sans forme d'onde), diagnostics avec secrets masqués.
