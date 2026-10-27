"""API client tests against the mock server (no Home Assistant needed)."""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.idratek_cortex.api import (
    CortexApiError,
    CortexClient,
    CortexConnectionError,
    parse_port_list,
)


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


def make(session, cortex, user="home", password="secret"):
    return CortexClient(session, "127.0.0.1", cortex.port, user, password)


async def test_object_list_with_bad_content_type(session, cortex):
    objects = await make(session, cortex).list_objects()
    assert len(objects) == 54
    by_id = {o.id: o for o in objects}
    assert by_id["76"].name == "Main Lights"  # display name, stray space removed
    assert by_id["76"].type == "Light"
    assert by_id["76"].parent == "Kitchen"


async def test_port_list_parsed_by_name(session, cortex):
    client = make(session, cortex)
    obj = next(o for o in await client.list_objects() if o.id == "76")
    ports = await client.list_ports(obj)
    assert ports["Turn On"].direction == "In"
    assert ports["Turn On"].index == 5
    assert ports["Set State (Output)"].direction == "Out"
    assert "EndList" not in ports


def test_port_list_handles_double_space_and_missing_prefix():
    text = "ListObjectPort  Main Lights.Turn On[In]\nListObjectPort Other.Turn Off[In]\nEndList\n"
    ports = parse_port_list(text, "Main Lights")
    assert set(ports) == {"Turn On", "Turn Off"}


async def test_read_port_by_name_and_numeric_404(session, cortex):
    client = make(session, cortex)
    assert await client.read_port("76", "Set State (Output)") == "0"
    with pytest.raises(CortexApiError) as err:
        await client.read_port("76", "10")  # numeric lookups are not reliable
    assert err.value.not_found


async def test_in_band_permission_error(session, cortex):
    with pytest.raises(CortexApiError) as err:
        await make(session, cortex).read_port("82", "Temperature")
    assert err.value.permission


async def test_wrong_password_is_anonymous_default(session, cortex):
    client = make(session, cortex, password="wrong")
    assert len(await client.list_objects()) == 54  # list is open to everyone
    with pytest.raises(CortexApiError) as err:
        await client.read_port("76", "Set State (Output)")
    assert err.value.permission
    assert "default" in err.value.message


async def test_command_changes_state(session, cortex):
    client = make(session, cortex)
    await client.command("525", "Turn On")
    assert await client.read_port("525", "Set State (Output)") == "100"
    await client.command("525", "Turn Off")
    assert await client.read_port("525", "Set State (Output)") == "0"
    assert ("POST", "/api/v1/Objects.json/525?Turn%20On=1") in cortex.requests


async def test_command_unknown_port_raises(session, cortex):
    with pytest.raises(CortexApiError) as err:
        await make(session, cortex).command("525", "Explode")
    assert err.value.not_found


async def test_connection_refused(session):
    client = CortexClient(session, "127.0.0.1", 1, "home", "x")
    with pytest.raises(CortexConnectionError):
        await client.list_objects()
