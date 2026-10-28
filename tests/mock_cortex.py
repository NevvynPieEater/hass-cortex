"""A mock Cortex web server that reproduces the behaviour seen on a real install.

Reproduced quirks (all taken from captured responses):
* malformed header  "Content-Type: Content-Type: application/JSON"
* errors are HTTP 200 with a body like "401 USER home not permitted to access X"
* numeric port lookups are unreliable; port-name lookups work
* the object list is readable by anyone; object detail needs a permitted user
* commands answer {"CortexAPI":{"Code":"200","Message":"OK"}}

The Temperature port layout was NOT captured (the test user was not permitted),
so the layout used here is an assumption and is marked as such.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

from aiohttp import web
import aiohttp

FIXTURES = Path(__file__).parent / "fixtures"

LIGHT_PORTS = [
    ("From Room Presence", "In"), ("Flash lights", "In"), ("External Light Level Input", "In"),
    ("Internal Light Level Input", "In"), ("Override mode", "ValueIn"), ("Turn On", "In"),
    ("Turn Off", "In"), ("Toggle", "In"), ("Speak", "In"), ("Internal Light Level State", "Out"),
    ("Set State (Output)", "Out"), ("Set On (Output)", "Out"), ("Set Off (Output)", "Out"),
    ("Enable", "In"), ("Disable", "In"), ("Display", "In"), ("Toggle and Synchronise", "In"),
    ("Synchronise (Output)", "Out"), ("Operating Mode", "ValueIn"), ("Timer stop", "In"),
    ("Timer start", "In"), ("Follow state (input)", "In"), ("On override change (output)", "Out"),
    ("Set to Stealth (input)", "In"), ("Timer Toggle", "In"), ("Icon off time", "ValueOut"),
    ("Icon on time", "ValueOut"),
]
BLIND_PORTS = [
    ("Relay 1", "Out"), ("Relay 2", "Out"), ("Close limit switch", "In"), ("Open limit switch", "In"),
    ("Default device if false", "In"), ("Default device if true", "In"),
    ("Inhibit motion if false", "In"), ("Inhibit motion if true", "In"),
    ("Set device open value", "ValueIn"), ("Edit device open value", "ValueIn"),
    ("Set State (Output) Analogue", "ValueOut"), ("Open", "In"), ("Close", "In"), ("Toggle", "In"),
    ("Stop", "In"), ("Override", "In"), ("Speak local", "In"), ("Speak broadcast", "In"),
    ("Display local", "In"), ("Display broadcast", "In"), ("On error", "Out"),
    ("Busy (Output)", "Out"), ("State (Output)", "Out"), ("Follow State (Input)", "In"),
    ("Open to position or stop", "ValueIn"), ("Tell devices position by observation", "ValueIn"),
    ("Enable", "In"), ("Disable", "In"), ("Busy", "Out"), ("Icon off time", "ValueOut"),
    ("Icon on time", "ValueOut"),
]
SOCKET_PORTS = [
    ("State input", "In"), ("Turn on", "In"), ("Turn off", "In"), ("Toggle", "In"),
    ("Pulse On", "In"), ("Pulse Off", "In"), ("Set State (Output)", "Out"),
    ("Speak local", "In"), ("Speak broadcast", "In"), ("Display local", "In"),
    ("Display broadcast", "In"), ("Toggle: pulse on, set off", "In"),
    ("Toggle: pulse off, set on", "In"), ("Block pulse inputs", "In"),
    ("Pulse On if already Off", "In"), ("Pulse Off if already On", "In"),
    ("Set On (Output)", "Out"), ("Set Off (Output)", "Out"), ("Icon off time", "ValueOut"),
    ("Icon on time", "ValueOut"),
]
# Layouts and sample values for every other type come from a real discovery run
# (sanitised): tests/fixtures/discovery.json.
DISCOVERY = json.loads((FIXTURES / "discovery.json").read_text())

LAYOUTS = {
    "Light": LIGHT_PORTS,
    "MotorControl": BLIND_PORTS,
    "OnOffLoad": SOCKET_PORTS,
    **{t: [tuple(p) for p in ports] for t, ports in DISCOVERY["layouts"].items()},
}

BAD_HEADER = {"Content-Type": "Content-Type: application/JSON"}
SYNAPSE_HEADER = {"Content-Type": "Content-Type: application/Synapse"}


class MockCortex:
    """In-process mock of the Cortex web server."""

    def __init__(self, user: str = "home", password: str = "secret") -> None:
        self.user = user
        self.password = password
        self.rows = json.loads((FIXTURES / "objects.json").read_text())["CortexAPI"]["CortexObject"]
        self.rows += DISCOVERY["rows"]
        self.by_id = {r["IDNumber"]: r for r in self.rows}
        # Types the test user may open (tests add e.g. "Temperature" to simulate a refusal).
        self.blocked_types: set[str] = set()
        self.state: dict[str, dict[str, str]] = {}
        for r in self.rows:
            t = r["ControlObjectType"]
            if t in ("Light", "OnOffLoad"):
                self.state[r["IDNumber"]] = {"Set State (Output)": "0"}
            elif t == "MotorControl":
                self.state[r["IDNumber"]] = {
                    "State (Output)": "100",
                    "Set State (Output) Analogue": "33.7424270131371",
                    "Busy": "0",
                }
            elif r["IDNumber"] in DISCOVERY["values"]:
                self.state[r["IDNumber"]] = dict(DISCOVERY["values"][r["IDNumber"]])
        self.requests: list[tuple[str, str]] = []
        self.runner: web.AppRunner | None = None
        self.port = 0

    # -------------------------------------------------------------------- helpers

    def _user(self, request: web.Request) -> str:
        header = request.headers.get("Authorization", "")
        if header.startswith("Basic "):
            try:
                creds = aiohttp.BasicAuth.decode(header, encoding="latin1")
            except ValueError:
                return "default"
            if creds.login == self.user and creds.password == self.password:
                return self.user
        return "default"

    @staticmethod
    def _text(body: str) -> web.Response:
        return web.Response(body=body.encode(), headers=SYNAPSE_HEADER)

    def _denied(self, request: web.Request, row: dict) -> str | None:
        user = self._user(request)
        if user == "default" or row["ControlObjectType"] in self.blocked_types:
            return f"401 USER {user} not permitted to access {row['FriendlyName'].strip()}"
        return None

    # ------------------------------------------------------------------- handlers

    async def object_list(self, request: web.Request) -> web.Response:
        self.requests.append(("GET", request.path_qs))
        return web.Response(
            body=json.dumps({"CortexAPI": {"CortexObject": self.rows}}, indent=2).encode(),
            headers=BAD_HEADER,
        )

    async def object_detail(self, request: web.Request) -> web.Response:
        self.requests.append(("GET", request.path_qs))
        row = self.by_id.get(request.match_info["id"])
        if row is None:
            return self._text("404 Object does not exist")
        if (msg := self._denied(request, row)) is not None:
            return self._text(msg)
        layout = LAYOUTS.get(row["ControlObjectType"])
        if layout is None:
            return self._text(f"404 No ports for {row['FriendlyName']}")
        name = row["FriendlyName"]
        lines = [f"ListObjectPort {name}.{port}[{direction}]" for port, direction in layout]
        return self._text("\n".join([*lines, "EndList"]) + "\n")

    async def port_read(self, request: web.Request) -> web.Response:
        self.requests.append(("GET", request.path_qs))
        row = self.by_id.get(request.match_info["id"])
        if row is None:
            return self._text("404 Object does not exist")
        if (msg := self._denied(request, row)) is not None:
            return self._text(msg)
        port = unquote(request.match_info["port"])
        values = self.state.get(row["IDNumber"], {})
        if port not in values:  # includes every numeric lookup
            return self._text("404 Port does not exist")
        return self._text(f"{row['FriendlyName']}.{port}={values[port]}\n")

    async def command(self, request: web.Request) -> web.Response:
        self.requests.append(("POST", request.path_qs))
        row = self.by_id.get(request.match_info["id"])
        if row is None:
            return self._text("404 Object does not exist")
        if (msg := self._denied(request, row)) is not None:
            return self._text(msg)
        if len(request.query) != 1:
            return self._text("404 Port does not exist")
        action = next(iter(request.query))
        values = self.state[row["IDNumber"]]
        t = row["ControlObjectType"]
        if t in ("Light", "OnOffLoad") and action.lower() == "turn on":
            values["Set State (Output)"] = "100"
        elif t in ("Light", "OnOffLoad") and action.lower() == "turn off":
            values["Set State (Output)"] = "0"
        elif t == "MotorControl" and action in ("Open", "Close", "Stop"):
            values["Busy"] = "1" if action != "Stop" else "0"
            if action == "Open":
                values["State (Output)"], values["Set State (Output) Analogue"] = "100", "100"
            elif action == "Close":  # closed = 0 is an assumption, not yet seen live
                values["State (Output)"], values["Set State (Output) Analogue"] = "0", "0"
        else:
            return self._text("404 Port does not exist")
        body = json.dumps({"CortexAPI": {"Code": "200", "Message": "OK"}}, indent=2)
        return web.Response(body=body.encode(), headers=BAD_HEADER)

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/api/v1/Objects.json/", self.object_list)
        app.router.add_get("/api/v1/Objects/{id}", self.object_detail)
        app.router.add_get("/api/v1/Ports/{id}/{port}", self.port_read)
        app.router.add_post("/api/v1/Objects.json/{id}", self.command)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]  # noqa: SLF001

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
