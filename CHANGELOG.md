# Changelog

## 1.0.0 – première version / first release
- Détection automatique du firmware (17.xx JSON, 16.xx texte) ; lecture seule pour une version non vérifiée.
- Découverte DHCP (`RMS-ESP32-*`) et routeurs connus d'un routeur déjà ajouté, avec confirmation.
- Modes Arrêt, Solaire seul, Solaire + garantie, Marche forcée ; pilotage externe qui expire après 30 min.
- Forçages temporaires de 30 min uniquement, aucune écriture dans la configuration du routeur.
- Sonde, coupure du thermostat ou énergie pour « ballon chaud » ; puissance déclarée, compteur dédié ou calibration.
- « Ouverture si forcée » réglable depuis la carte en 17.xx (écrite seulement à la demande de l'utilisateur).
- Carte Lovelace bilingue (sans forme d'onde), diagnostics avec secrets masqués.
