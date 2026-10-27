"""Shared fixtures."""

from __future__ import annotations

import pytest

from .mock_cortex import MockCortex

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow the custom integration to load in tests."""
    yield


@pytest.fixture(autouse=True)
def allow_localhost_sockets(socket_enabled):
    """The mock Cortex server needs a real localhost socket."""
    yield


@pytest.fixture
async def cortex():
    """Run a mock Cortex server on localhost."""
    server = MockCortex()
    await server.start()
    yield server
    await server.stop()
