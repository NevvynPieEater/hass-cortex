# Idratek Cortex

Read and control an [Idratek Cortex](https://www.idratek.com) home automation system from Home Assistant, locally.

The Cortex Web API is undocumented. This integration is built from captured replies of a real installation.

---

## Features

- Lights (on / off)
- Motorised blinds (open / close / stop, with position and open/closed state)
- On/off loads such as sockets
- Temperature and humidity sensors
- Door, motion and property presence (occupancy) sensors
- Boiler, heat zone, HVAC and fan state
- Config flow (UI setup), reconfigure and polling-interval option
- Rooms become Home Assistant devices, so entities are named like `light.kitchen_main_lights`
- Diagnostics download (login and address redacted)

---

## Status

| Cortex object | Home Assistant entity | State |
|---|---|---|
| Light | `light` | Read and control verified on a real system |
| OnOffLoad | `switch` | Read verified, commands not yet tried live |
| MotorControl | `cover` | Read verified (State 100 = open, analogue = % open); commands not yet tried live |
| Temperature | `sensor` (°C) | Read verified on a real system |
| Humidity | `sensor` (%, plus a dew point sensor that is disabled by default) | Read verified |
| LightLevel | `sensor` (raw value, unit unconfirmed) and a `binary_sensor` "Dark" | Read verified |
| Door | `binary_sensor` (door) | Read verified. Assumes `Door output state` 100 = open (not yet confirmed on site) |
| Motion | `binary_sensor` (motion) | Read verified |
| PIR | `binary_sensor` (motion) | Read verified; trigger not yet seen |
| Room | `binary_sensor` (occupancy) per room, plus a delayed occupancy sensor that is disabled by default | Read verified |
| House | `binary_sensor` (occupancy), vacant mode, unoccupied over 24 hours | Read verified |
| Boiler, HeatZone, FanControl | `binary_sensor` (running / heat) | Read verified |
| HVAC | heating and cooling demand `binary_sensor`s, set-point `sensor`s | Read verified |

Intercom and button panels (`Buttons122`) are not exposed yet.

Tested with a mock Cortex built from real replies (31 automated tests) on Home Assistant 2026.2.3.
Not yet run against a live Cortex from inside Home Assistant.

---

## Installation (HACS)

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=home-assistant&logoColor=white)](https://hacs.xyz/)

1. Open HACS
2. Go to Integrations
3. Add this repository as a custom repository (category: Integration)
4. Install "Idratek Cortex"
5. Restart Home Assistant

Manual: copy `custom_components/idratek_cortex` into your Home Assistant `config/custom_components/` folder and restart.

Needs Home Assistant 2024.11 or newer.

---

## Cortex setup

1. You need the Cortex Web Server and Cortex Mobile licences.
2. Create a user for Home Assistant on the Web Server object (Behaviour, Authorised Users).
3. Give that user access to each object you want in Home Assistant: view for sensors, doors and motion, view and control for lights, blinds and sockets.

Note: Cortex does not ask for a login. A wrong or missing login is treated as an anonymous user that can list
objects but not open them.

---

## Configuration

Add the integration from:

Settings → Devices & Services → Add Integration → Idratek Cortex

You will need:

- The address of the Cortex PC as seen from Home Assistant (e.g. `192.168.1.50`)
- The web server port (HTTP is commonly `8000`; HTTPS on `443` uses a self-signed certificate, so leave certificate checking off)
- The Cortex Web API username and password

If you change permissions in Cortex, reload the integration to pick them up.

---

## Notes

- Polls every 30 seconds by default (5 seconds minimum, set in the integration options). Roughly 70 small requests per cycle.
- Cortex reports problems inside normal replies (for example `401 USER x not permitted...`). These show as unavailable entities or as an error when a button is pressed.
- The login is sent as HTTP Basic. Use HTTPS if the network is not trusted.
- Not built yet: webhook push updates, floors, setting a blind to a specific position.

---

## Development

```
pip install -r requirements_test.txt
pytest
```

The tests run a mock Cortex server on localhost that reproduces the quirks of the real one (malformed `Content-Type`
header, errors returned with HTTP 200, port names working where numbers do not).

---

## Links

- 🏠 [Home Assistant](https://www.home-assistant.io/)
- 📦 [HACS](https://hacs.xyz/)
- 📖 [Documentation](https://github.com/NevvynPieEater/hass-cortex)
- 🐞 [Report an Issue](https://github.com/NevvynPieEater/hass-cortex/issues)

---

## Support / Donate

If you find this useful:

☕ Buy me a coffee  
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-yellow.svg?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/nevvyn)

---

## Disclaimer

This project is not affiliated with Idratek.
