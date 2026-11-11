# Changelog

## 0.2.9 (unreleased)

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
