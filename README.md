# yeedi for Home Assistant

A Home Assistant integration for **yeedi** robot vacuums (yeedi vac max, vac 2, vac 2 pro, vac hybrid, vac station, 2 hybrid, mop station), through the yeedi cloud account.

yeedi is an Ecovacs brand: the robots speak the same protocol as the Deebots, but the official Ecovacs integration cannot log into a yeedi account. This integration logs in with the yeedi application identity and reuses [deebot-client](https://github.com/DeebotUniverse/client.py), the library behind the official integration, with the yeedi specifics added (login, model sheets, map discovery).

## Features

- Configuration in the UI (e-mail, password, country), credentials stored by Home Assistant
- `vacuum` entity: start, pause, stop, return to dock, locate, fan speed (Standard / Max / Max+) and **mop only** (vacuum motor off)
- Room cleaning with the native **segments** of Home Assistant (`vacuum.clean_area`), rooms cleaned in the order given
- `vacuum.send_command` with `spot_area` (`rooms: "2,1,3"`) and `custom_area`
- Sensors: battery, error, area and duration of the last cleaning, totals, consumables (main brush, filter, side brush)
- **Suction power** select (Standard / Max / Max+ / mop only) and **water flow level** select
- **Map card included**: rooms, dock, robot and trace of the current cleaning, room selection by tapping the map

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

## Map card

The integration ships its own Lovelace card, loaded automatically (no extra resource to add):

```yaml
type: custom:yeedi-map-card
entity: vacuum.yeedi_vac_max
title: Vacuum          # optional
controls: true         # optional: buttons, suction and water level under the map
room_names:            # optional: your own room names (room id -> name)
  2: Living room
  3: Bedroom
```

Tap rooms to choose them (the numbers give the cleaning order), then **Clean**. With no room chosen, **Clean** starts a full cleaning. The trace is drawn from the positions the robot reports while it cleans.

If the robot does not report the outline of its rooms, the card shows them as a list to choose from instead of a map.

## Known limitations

- Room names are the generic ones reported by the robot (Living room, Bedroom…). Custom names from the yeedi app are not available through the cloud API.
- No map image (walls and floor) as in the yeedi app: the card draws the outline of the rooms reported by the robot.
- The robot does not report the mop-only setting: the integration keeps the last one set from Home Assistant (changing it in the yeedi app is not seen).
- The account must not require a device verification e-mail more than once; if yeedi asks for a code, the flow will prompt for it.

## Credits

- [deebot-client](https://github.com/DeebotUniverse/client.py) and the Home Assistant Ecovacs integration, which this integration is built on.
- [ecovacs-deebot.js](https://github.com/mrbungle64/ecovacs-deebot.js), whose yeedi support documented the login differences.

