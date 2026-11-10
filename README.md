# yeedi for Home Assistant

A Home Assistant integration for **yeedi** robot vacuums (yeedi vac max, vac 2, vac 2 pro, vac hybrid, vac station, 2 hybrid, mop station), through the yeedi cloud account.

yeedi is an Ecovacs brand: the robots speak the same protocol as the Deebots, but the official Ecovacs integration cannot log into a yeedi account. This integration logs in with the yeedi application identity and reuses [deebot-client](https://github.com/DeebotUniverse/client.py), the library behind the official integration, with the yeedi specifics added (login, model sheets, map discovery).

*Version française plus bas.*

## Features

- Configuration in the UI (e-mail, password, country), credentials stored by Home Assistant
- `vacuum` entity: start, pause, stop, return to dock, locate, fan speed (Standard / Max / Max+)
- Room cleaning with the native **segments** of Home Assistant (`vacuum.clean_area`), rooms cleaned in the order given
- `vacuum.send_command` with `spot_area` (`rooms: "2,1,3"`) and `custom_area`
- Sensors: battery, error, area and duration of the last cleaning, totals, consumables (main brush, filter, side brush)
- Water flow level select
- Live position events from the robot (for custom cards)

Tested with a yeedi vac max (class `04z443`) on Home Assistant 2026.11.

## Installation

### HACS

1. HACS → Integrations → ⋮ → *Custom repositories*, add `https://github.com/ciscouf-ops/ha-yeedi` as an *Integration*.
2. Install **yeedi**, restart Home Assistant.
3. Settings → Devices & services → *Add integration* → **yeedi**, enter the account used in the yeedi app.

### Manual

Copy `custom_components/yeedi` into your `config/custom_components/` folder and restart Home Assistant.

## Room cleaning

Rooms are exposed as segments: in the UI, the vacuum's more-info dialog lets you pick rooms. In an automation:

```yaml
action: vacuum.clean_area
target:
  entity_id: vacuum.yeedi
data:
  segments:
    - "874128701_2"   # <map id>_<room id>, as listed by the entity
```

or with the raw room ids:

```yaml
action: vacuum.send_command
target:
  entity_id: vacuum.yeedi
data:
  command: spot_area
  params:
    rooms: "2,1,3"
    cleanings: 1
```

The room ids and names are in the `rooms` attribute of the vacuum entity.

## Known limitations

- Room names are the generic ones reported by the robot (Living room, Bedroom…). Custom names from the yeedi app are not available through the cloud API.
- No map image yet.
- Mop-only mode (`setMopMute`) is not exposed yet; it can be sent with `vacuum.send_command` (`command: setMopMute`, `params: {enable: 1}`).
- The account must not require a device verification e-mail more than once; if yeedi asks for a code, the flow will prompt for it.

## Credits

- [deebot-client](https://github.com/DeebotUniverse/client.py) and the Home Assistant Ecovacs integration, which this integration is built on.
- [ecovacs-deebot.js](https://github.com/mrbungle64/ecovacs-deebot.js), whose yeedi support documented the login differences.

---

# yeedi pour Home Assistant

Intégration Home Assistant pour les aspirateurs robots **yeedi**, via le compte yeedi (cloud).

yeedi est une marque d'Ecovacs : les robots parlent le même protocole que les Deebot, mais l'intégration Ecovacs officielle ne sait pas se connecter à un compte yeedi. Cette intégration se connecte avec l'identité de l'application yeedi et réutilise deebot-client, la bibliothèque de l'intégration officielle, en y ajoutant ce qui est propre à yeedi (connexion, fiches des modèles, découverte de la carte).

## Fonctions

- Configuration dans l'interface (e-mail, mot de passe, pays), identifiants conservés par Home Assistant
- Entité `vacuum` : démarrer, pause, stop, retour base, localiser, vitesse (Standard / Max / Max+)
- Nettoyage par pièce avec les **segments** natifs de Home Assistant (`vacuum.clean_area`), pièces nettoyées dans l'ordre donné
- `vacuum.send_command` avec `spot_area` (`rooms: "2,1,3"`) et `custom_area`
- Capteurs : batterie, erreur, surface et durée du dernier nettoyage, totaux, consommables
- Sélecteur de débit d'eau
- Position du robot en temps réel (pour des cartes personnalisées)

Testé avec un yeedi vac max (classe `04z443`) sur Home Assistant 2026.11.

## Installation

Via HACS : dépôt personnalisé `https://github.com/ciscouf-ops/ha-yeedi` (type *Intégration*), installer **yeedi**, redémarrer, puis Paramètres → Appareils et services → Ajouter une intégration → **yeedi**.

Manuellement : copier `custom_components/yeedi` dans `config/custom_components/` et redémarrer.

## Limites connues

- Les noms des pièces sont ceux, génériques, renvoyés par le robot. Les noms donnés dans l'application yeedi ne sont pas accessibles.
- Pas encore d'image de la carte.
- Le mode serpillère seule n'est pas encore exposé (`vacuum.send_command`, `command: setMopMute`, `params: {enable: 1}`).
