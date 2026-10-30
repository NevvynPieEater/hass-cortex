"""Constants for the Idratek Cortex integration."""

from __future__ import annotations

DOMAIN = "idratek_cortex"

CONF_SSL = "ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 8000
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

# Cortex is a small Windows service; keep concurrent requests low.
MAX_CONCURRENCY = 4
REQUEST_TIMEOUT = 10  # seconds
# Pause after a command before reading the new state back.
COMMAND_SETTLE_DELAY = 0.5  # seconds
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

# ControlObjectType values seen in a real installation.
TYPE_LIGHT = "Light"
TYPE_ONOFF = "OnOffLoad"
TYPE_BLIND = "MotorControl"
TYPE_TEMPERATURE = "Temperature"
TYPE_HUMIDITY = "Humidity"
TYPE_LIGHT_LEVEL = "LightLevel"
TYPE_DOOR = "Door"
TYPE_MOTION = "Motion"
TYPE_PIR = "PIR"
TYPE_HOUSE = "House"
TYPE_BOILER = "Boiler"
TYPE_HEAT_ZONE = "HeatZone"
TYPE_FAN = "FanControl"
TYPE_HVAC = "HVAC"
TYPE_ROOM = "Room"

# Per type: which ports are read for state (role -> exact Cortex port name).
# Port names (not numbers) are used because numeric lookups were inconsistent
# on real hardware while name lookups worked every time.
STATE_PORTS: dict[str, dict[str, str]] = {
    TYPE_LIGHT: {"state": "Set State (Output)"},
    TYPE_ONOFF: {"state": "Set State (Output)"},
    TYPE_BLIND: {
        "state": "State (Output)",
        "position": "Set State (Output) Analogue",
        "busy": "Busy",
    },
    # Read-only types. Port names taken from a real Cortex port list; values
    # are 0 / 100 for on/off style outputs.
    TYPE_TEMPERATURE: {"state": "Temperature Output"},
    TYPE_HUMIDITY: {"state": "Humidity Output", "dewpoint": "Dewpoint Output"},
    TYPE_LIGHT_LEVEL: {"state": "Light Level Output", "dark": "Dark Output"},
    TYPE_DOOR: {"state": "Door output state", "fault": "Fault"},
    TYPE_MOTION: {"state": "Output", "long": "Long motion sense output", "fault": "Fault"},
    TYPE_PIR: {"state": "Output", "long": "Long motion sense output", "fault": "Fault"},
    TYPE_HOUSE: {
        "state": "Presence state output",
        "vacant": "Vacant state output",
        "unoccupied_24h": "Unoccupied > 24Hrs state output",
    },
    TYPE_BOILER: {"state": "Set State (Output)", "demand": "Demand for extra heating"},
    TYPE_HEAT_ZONE: {"state": "Set State (Output)", "to_boiler": "Output To Boiler"},
    TYPE_FAN: {"state": "Set State (Output)"},
    TYPE_ROOM: {
        "state": "Occupied state output",
        "delayed": "Delayed occupied state output",
    },
    TYPE_HVAC: {
        "heating": "To Zone Valve or Boiler",
        "cooling": "To Damper or AC",
        "heating_setpoint": "Heating Setpoint (Output)",
        "cooling_setpoint": "Cooling Setpoint (Output)",
    },
}

# Per type: command key -> exact Cortex input port name.
# Types not listed here are read-only.
COMMAND_PORTS: dict[str, dict[str, str]] = {
    TYPE_LIGHT: {"on": "Turn On", "off": "Turn Off"},
    TYPE_ONOFF: {"on": "Turn on", "off": "Turn off"},
    TYPE_BLIND: {"open": "Open", "close": "Close", "stop": "Stop"},
}

# Seconds after a blind command at which its state is read again.
BLIND_REFRESH_DELAYS = (10, 30)
