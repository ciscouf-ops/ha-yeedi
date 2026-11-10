# Changelog

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
