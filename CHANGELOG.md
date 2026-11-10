# Changelog

## 0.2.5
- Map card: room names follow the Home Assistant area each room is associated with (vacuum entity settings), then the card's own `room_names`, then the robot.
- Map card: icon chips for suction and water levels, robot drawn on the dock, visual editor with room names.
- Room outlines kept in storage and requested again when a cleaning starts.
- Suction power select (shared with the vacuum fan speed, incl. mop only).
- Brand images.
- Robustness: a robot that fails to initialize no longer blocks the others; an unreadable saved map starts empty; mop only is cleared when the suction level is changed from the yeedi app.

## 0.1.0
- First version: yeedi account, vacuum entity, sensors, water level, rooms as segments.
