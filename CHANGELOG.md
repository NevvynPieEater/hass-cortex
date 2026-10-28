# Changelog

All notable changes to this project are listed here. Versions below 1.0 are
still being checked against live systems.

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
