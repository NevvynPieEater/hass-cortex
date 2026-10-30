"""Client for the Idratek Cortex Web API.

The behaviour below was derived from captured responses of a real installation and
checked against the Web API pages of the Cortex 27 help file (which gives the
resource names and port-set syntax but not the quirks of the replies):

* Object list:   GET  /api/v1/Objects.json/            -> JSON
* Port list:     GET  /api/v1/Objects/<id>              -> text, "ListObjectPort ..." lines
* Read a port:   GET  /api/v1/Ports/<id>/<port name>    -> text, "<object>.<port>=<value>"
* Command:       POST /api/v1/Objects.json/<id>?<port name>=1 -> JSON {"CortexAPI":{"Code":"200",...}}

Quirks handled here:

* The ``Content-Type`` header is malformed ("Content-Type: application/JSON"),
  so bodies are always read as raw text and parsed by hand.
* Errors arrive with HTTP status 200 and a body such as
  "401 USER home not permitted to access Kitchen Temperature".
* Names may have stray leading/trailing spaces.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import re
from urllib.parse import quote

import aiohttp
from yarl import URL

from .const import MAX_CONCURRENCY, MAX_RESPONSE_BYTES, REQUEST_TIMEOUT

_ERROR_RE = re.compile(r"^(\d{3})\s+(.*)$", re.DOTALL)
_PORT_LINE_RE = re.compile(r"^(?P<label>.*)\[(?P<direction>[A-Za-z]+)\]\s*$")


class CortexError(Exception):
    """Base error."""


class CortexConnectionError(CortexError):
    """Cortex could not be reached, or the reply was unusable."""


class CortexApiError(CortexError):
    """Cortex answered with an in-band error (e.g. 401, 404)."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"{code} {message}")
        self.code = code
        self.message = message

    @property
    def permission(self) -> bool:
        """Return True if the user is not permitted to access the object."""
        return self.code == 401

    @property
    def not_found(self) -> bool:
        """Return True if the object or port does not exist."""
        return self.code == 404


@dataclass
class CortexPort:
    """One port of a Cortex object."""

    name: str
    direction: str  # In, Out, ValueIn, ValueOut
    index: int


@dataclass
class CortexObject:
    """One object from the object list."""

    id: str
    name: str
    type: str
    parent: str
    ports: dict[str, CortexPort] = field(default_factory=dict)


def _quote(value: str) -> str:
    """Percent-encode like the requests that were verified on real hardware.

    Spaces become %20; parentheses are left as they were in the tested URLs.
    """
    return quote(value, safe="()")


def parse_object_list(text: str) -> list[CortexObject]:
    """Parse the JSON object list."""
    try:
        data = json.loads(text)
        raw = data["CortexAPI"]["CortexObject"]
    except (ValueError, KeyError, TypeError) as err:
        raise CortexConnectionError("Unexpected object list format") from err
    if isinstance(raw, dict):  # a single object may not be wrapped in a list
        raw = [raw]
    if not isinstance(raw, list):
        raise CortexConnectionError("Unexpected object list format")

    objects: dict[str, CortexObject] = {}
    for row in raw:
        if not isinstance(row, dict):
            continue
        ident = str(row.get("IDNumber", "")).strip()
        if not ident or ident in objects:
            continue
        name = str(row.get("Prompt.Display.Name") or row.get("FriendlyName") or "").strip()
        objects[ident] = CortexObject(
            id=ident,
            name=name or f"Object {ident}",
            type=str(row.get("ControlObjectType", "")).strip(),
            parent=str(row.get("Parent", "")).strip(),
        )
    return list(objects.values())


def parse_port_list(text: str, object_name: str) -> dict[str, CortexPort]:
    """Parse "ListObjectPort <object>.<port>[<dir>]" lines."""
    ports: dict[str, CortexPort] = {}
    prefix = object_name.strip() + "."
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("ListObjectPort"):
            continue
        body = line[len("ListObjectPort") :].strip()
        match = _PORT_LINE_RE.match(body)
        if not match:
            continue
        label = match["label"].strip()
        if label.startswith(prefix):
            port_name = label[len(prefix) :]
        elif "." in label:
            port_name = label.split(".", 1)[1]
        else:
            port_name = label
        port_name = port_name.strip()
        if port_name and port_name not in ports:
            ports[port_name] = CortexPort(port_name, match["direction"], len(ports))
    return ports


class CortexClient:
    """Async client for the Cortex Web API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        *,
        ssl: bool = False,
    ) -> None:
        """Initialise the client."""
        self._session = session
        host = host.strip()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        scheme = "https" if ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self._api = f"{self.base_url}/api/v1/"
        # Cortex never challenges for credentials, so Basic auth is sent up front.
        self._auth = (
            aiohttp.BasicAuth(username, password, encoding="latin1") if username else None
        )
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def _request(self, method: str, path: str) -> str:
        """Make a request and return the body, raising for in-band errors."""
        url = URL(self._api + path, encoded=True)
        async with self._semaphore:
            try:
                async with self._session.request(
                    method,
                    url,
                    auth=self._auth,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                ) as response:
                    status = response.status
                    body = await response.read()
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                raise CortexConnectionError(f"Cannot reach Cortex: {err}") from err

        if len(body) > MAX_RESPONSE_BYTES:
            raise CortexConnectionError("Response too large")
        text = body.decode("utf-8", errors="replace").strip()
        if status != 200:
            raise CortexApiError(status, text[:200] or "HTTP error")

        match = _ERROR_RE.match(text)
        if (
            match
            and "=" not in text
            and not text.startswith(("{", "ListObjectPort"))
        ):
            raise CortexApiError(int(match[1]), match[2].strip())
        return text

    async def list_objects(self) -> list[CortexObject]:
        """Return all objects visible to the configured user."""
        return parse_object_list(await self._request("GET", "Objects.json/"))

    async def list_ports(self, obj: CortexObject) -> dict[str, CortexPort]:
        """Return the ports of an object."""
        text = await self._request("GET", f"Objects/{_quote(obj.id)}")
        return parse_port_list(text, obj.name)

    async def read_port(self, object_id: str, port_name: str) -> str:
        """Read a port by name and return its value as text."""
        text = await self._request(
            "GET", f"Ports/{_quote(object_id)}/{_quote(port_name)}"
        )
        _, sep, value = text.rpartition("=")
        if not sep:
            raise CortexConnectionError(f"Unexpected port reply: {text[:80]!r}")
        return value.strip()

    async def command(self, object_id: str, port_name: str) -> None:
        """Trigger an input port (sets it to 1)."""
        text = await self._request(
            "POST", f"Objects.json/{_quote(object_id)}?{_quote(port_name)}=1"
        )
        try:
            result = json.loads(text)["CortexAPI"]
            code = int(result["Code"])
            message = str(result.get("Message", ""))
        except (ValueError, KeyError, TypeError) as err:
            raise CortexConnectionError(f"Unexpected command reply: {text[:80]!r}") from err
        if code != 200:
            raise CortexApiError(code, message)
