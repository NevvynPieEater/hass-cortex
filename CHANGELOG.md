# Changelog

All notable changes to this project are listed here. Versions below 1.0 are
still being checked against live systems.

## 0.5.0

### Added
- Instant updates pushed from Cortex. The integration now has a Home Assistant webhook
  (address shown under Configure). A Cortex Web API Client item that calls it with
  `object`, `port` and `value` updates the matching entity at once, for any watched
  state port (PIRs, doors, lights, temperatures and so on). A button panel press port
  above 0 fires that button's event. Polling carries on as a fallback. The webhook is
  limited to the local network.
- Button polling is now off by default (interval 0): presses are expected by push. Set a
  button polling interval of 1 to 3 seconds in Configure to turn the fast poller back on.

## 0.4.0

### Added
- Button panels (`Buttons122`): one `event` entity per button with `single_click`,
  `double_click` and `long_press` events. Cortex button outputs stay high for a few
  seconds, so a separate poller reads only those ports every 2 seconds (option
  "Button polling interval", 1 to 60 s). A press is the output rising from 0 to 100;
  a button already high at start-up does not fire. Names are generic ("Kitchen Buttons 4");
  rename them in Home Assistant. Pushed events (a webhook) would be better but Cortex's
  push format has not been found.
- `PIR` objects (dry-contact PIR inputs) now appear as motion `binary_sensor`s, with the
  long-motion and fault ports as attributes. Ports match the existing Motion type;
  a live trigger has not yet been captured.

## 0.3.0

### Added
- Occupancy `binary_sensor` for every Cortex room, on the same device as the
  room's lights and blinds. A delayed occupancy sensor is also created for each
  room but is disabled by default.
- Brand icons refreshed (256px and 512px).

### Not yet verified on a live system
- Blind commands (open, close, stop) and the on/off socket commands.
- Door sensors treat an output of 100 as open. This has not been confirmed on site.

## 0.2.0

### Added
- Temperature sensors now use the confirmed `Temperature Output` port.
- Humidity sensors, plus a dew point sensor that is disabled by default.
- Light level sensor and a "Dark" binary sensor.
- Door, motion and property presence (occupancy) binary sensors.
- Boiler, heat zone, HVAC and fan state, and HVAC heating and cooling set-points.
- `binary_sensor` platform.

### Changed
- Entity names collapse stray double spaces in Cortex names.
- Test suite now uses a sanitised capture from a real system (30 tests).

## 0.1.0

First release.

### Added
- Lights (on / off), motorised blinds (open / close / stop, position and
  open/closed state) and on/off loads such as sockets.
- Config flow with reconfigure and a polling-interval option.
- Rooms become Home Assistant devices.
- Diagnostics download with login and address redacted.
