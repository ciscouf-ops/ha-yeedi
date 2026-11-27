# Changelog

## 0.2.14b4 (test version)
- **Map card: choose what it shows.** Every part can be hidden, from the card editor ("What the card shows") or with `show:` in YAML: name, state, battery, water alerts, map, room names, no-mop zones and walls, dock, robot, trace, buttons, zone, suction, water, station and the last cleaning line. Without the map, the rooms show as buttons. `controls: false` still works.

## 0.2.14b3 (test version)
- **New: "Wash the mop" and "Dry the mop" buttons** for mop-washing stations (M16 Infinity). Their station is built in, so these buttons and "Empty the dustbin" are created without the station option.
- **Map card: a "Station" row**, shown only while the robot is docked and only with the actions its station has: empty on auto-empty stations, plus wash and dry on mop-washing stations.

## 0.2.14b2 (test version)
- **Map card**: an empty clean water tank or a full dirty water tank shows under the robot state, in orange, only while it lasts.
- **Map card: the water flow of the M16 Infinity** (a number from 0 to 50) now shows as a 5-step gauge, like the water levels of the other models. It was missing.

## 0.2.14b1 (test version)
- **New: "Clean water tank empty" and "Dirty water tank full"** problem sensors, for the stations that wash the mop (M16 Infinity). The station measures no water level, it only reports these as errors (codes 301/322 and 302/305/318/323): the sensors turn on with them and off when the robot reports no error. Suggested by @majorbig4 (#2).

## 0.2.13

### yeedi M16 Infinity (class `4e64gs`)
- **Now supported.** It has the hardware of the Ecovacs DEEBOT T90 Omni (OZMO Roller 3.0 mop, omni station), so it uses the deebot-client capabilities of the DEEBOT T90 Pro Omni, cleaning with `clean_V2`. Tested by @majorbig4 on two robots: cleaning, return to dock, suction levels and mop only, water flow, battery, consumables and statistics work (#2).
- **Room outlines on the map.** Same cause as on the yeedi vac station: the outlines come in `onMapInfo_V2`, in the same format, but marked as an Ecovacs message, which ha-yeedi left to deebot-client. They are now read too, for every robot built on a recent Ecovacs.
- New **Water flow** number (0-50) for robots that set the water with a number instead of levels; the water select stays for the others.
- **Fix: downloading the diagnostics failed** on these robots.

### Models nobody has tested yet
Lessons from the yeedi vac station and the M16 Infinity:
- **Cleaning**: a robot that answers "rcp not support" to `clean` is sent `clean_V2` instead (start, pause, stop, rooms, zones).
- **Emptying the dustbin**: a station that does not know `stationAction` is emptied with `setAutoEmpty act:start`, the yeedi vac station way.
- **Auto-empty**: a station that reports auto-empty on without a frequency gets an Off / On select instead of the frequencies.

These only kick in when the robot rejects the usual command: nothing changes for the models that already work.
- **Unknown models are set up in experimental mode** instead of being left out: a yeedi robot whose class nobody has reported yet (for example a recent M12 Pro+ or S20 Infinity Ultra) starts from the M16 Infinity base, cleaning with `clean_V2` first then `clean`, and the log asks its owner to open an issue.

### HACS
- **HACS shows the number of downloads**: each release now carries a `yeedi.zip`, built by GitHub, which HACS installs and counts.

## 0.2.12
- **Fix: emptying the dustbin did nothing on the yeedi vac station (`mnx7f4`).** This robot does not know `stationAction`; it empties with `setAutoEmpty` and `act: start`. Its auto-empty has no frequency either, so the select offers only Off / On there. Thanks @slevin-7 (#1).
- The auto-empty select asks the robot again after a change, so it no longer keeps showing the old value.
- **Fix: no room outlines on the map of the yeedi vac station.** This model always answers `getMapSubSet` with an empty outline and sends the outlines in an `onMapInfo_V2` message instead, which is now read. Ecovacs messages are left to deebot-client. Thanks @slevin-7 (#3).

## 0.2.11
- **License: the integration is now GPL-3.0-or-later** (it was MIT). `auth.py` adapts login methods from deebot-client, which is GPL-3.0, so the project has to follow that license.
- A `NOTICE` file and file headers credit the code derived from deebot-client (GPL-3.0) and from the Home Assistant Ecovacs integration (Apache-2.0, Copyright Home Assistant authors).
- No functional change.

## 0.2.10
- **Fix: after a Home Assistant restart, "Last cleaning" showed the restart time and 0 min.** When it connects, the robot reports the statistics of an empty session (0 m², a few seconds). These are now ignored (under 60 s with no area), and the last cleaning's area and duration are restored after a restart, with the time it ended in an `end` attribute.
- Map card: "Last cleaning" uses that `end` attribute when it is there.

## 0.2.9

### Map card
- The surface of a drawn zone is shown in its middle, counting only the floor inside the rooms (not the empty space around the map).
- The zone or the rooms sent to the robot stay highlighted on the map until it is back on the dock.

## 0.2.8
- **Fix: zone cleaning (and `clean_rooms` with two-digit room numbers) sent garbage to the robot.** deebot-client's `CleanArea` joins the coordinates itself, and the integration handed it a string, which was split character by character: the robot received a rectangle like `0,1,3,6` instead of the zone drawn, cleaned a few strips near the dock and went back. Lists are passed now; `custom_area` checks it gets four values.
- New sensors during a cleaning: current room, remaining time and estimated end. The integration learns how long each room takes (kept in storage) and the order of a full cleaning; the map card shows the room, the end time and a progress bar under the controls.
- Map card: room outlines cleaned up (steps shorter than 22 cm absorbed, angles kept straight), room labels sized to the room and split on two lines when needed, map capped at 560 px wide on large screens.
- Map card: with no room selected the button reads "Clean everything"; in zone mode it stays greyed out until a rectangle is drawn.
- Map card: after Clean / Pause / Resume / Dock, the button is greyed out with a spinner until the robot reports its new state (15 s at most), so it cannot be tapped twice.
- Map card: the trace is a single band as wide as the robot on a smoothed path, and the robot glides between two reported positions instead of jumping; while cleaning, the card updates the robot, the trace and the footer in place rather than rebuilding itself.

## 0.2.7
- Zones: the robot does a rectangle thinner than ~1 m in one straight line, so the card and `yeedi.clean_zone` widen each side to at least 1 m around the rectangle drawn.

## 0.2.6
- Map card: with one room selected, the button names it ("Clean Kitchen").
- Option *Auto-empty station* (integration → Configure, off by default): the "Empty the dustbin" button and the auto-empty select exist only when it is on, since the station is optional on the vac max and others.
- Durations shown rounded (minutes without decimals, hours with one).
- New entities: buttons (empty the dustbin, relocate, reset each consumable counter, clear the map — disabled by default), switches (continuous cleaning, carpet boost, advanced mode), volume number, auto-empty select (off / automatic / smart).
- Actions `yeedi.clean_rooms` (room numbers or names, 1–2 passes) and `yeedi.clean_zone` (rectangle in metres), with UI schemas.
- README: entities, actions, four up-to-date screenshots of the card (cleaning, rooms, zone, dark theme).
- Model table: yeedi cube and mop station pro added, Floor 3 family left to deebot-client, README table of models and dock kinds.
- Map card: zone cleaning (draw a rectangle on the map); no-mop zones and virtual walls from the yeedi app are drawn.
- Test suite (pytest) run in CI; a segment id without a room number is ignored; the map is saved immediately when the integration unloads.
- German, Spanish and Italian translations (integration and card).
- Map card: drawn battery gauge in the header (level fill, percentage inside, colour: green ≥50 %, orange, red <20 %, blue with a bolt while charging).
- Map card: last cleaning (duration, area, when) under the settings; a bogus robot position no longer squashes the map.
- Diagnostics download from the device page (credentials and identifiers redacted).
- Card URL carries a fingerprint of the file: browsers reload the card after an update.
- Map card: selected rooms stand out (others dimmed, coloured outline, numbered badge).
- Map card: room names follow the Home Assistant area each room is associated with (vacuum entity settings), then the card's own `room_names`, then the robot.
- Map card: suction and water as level gauges (mop only toggles on the suction gauge), robot drawn on the dock, visual editor with room names.
- Room outlines kept in storage and requested again when a cleaning starts.
- Suction power select (shared with the vacuum fan speed, incl. mop only).
- Brand images.
- Robustness: a robot that fails to initialize no longer blocks the others; an unreadable saved map starts empty; mop only is cleared when the suction level is changed from the yeedi app.

## 0.1.0
- First version: yeedi account, vacuum entity, sensors, water level, rooms as segments.
