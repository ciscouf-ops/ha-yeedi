"""Shared fixtures: fake robot pieces, so the tests need no cloud and no MQTT."""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import MagicMock

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/yeedi."""
    return


class FakeEventBus:
    """Records subscriptions and refresh requests; `emit` calls the handlers."""

    def __init__(self) -> None:
        self.handlers = defaultdict(list)
        self.refreshed: list[type] = []

    def subscribe(self, event_type, handler):
        self.handlers[event_type].append(handler)

        def unsubscribe() -> None:
            self.handlers[event_type].remove(handler)

        return unsubscribe

    def request_refresh(self, event_type) -> None:
        self.refreshed.append(event_type)

    async def emit(self, event) -> None:
        for handler in list(self.handlers[type(event)]):
            await handler(event)


class FakeDevice:
    """The parts of deebot_client.Device the integration touches."""

    def __init__(self, did: str = "did123", capabilities=None) -> None:
        self.device_info = {"did": did, "name": "SN", "class": "04z443", "nick": "yeedi"}
        self.events = FakeEventBus()
        self.capabilities = capabilities if capabilities is not None else MagicMock()
        self.commands: list = []
        self.fw_version = "1.0"
        self.mac = None

    async def execute_command(self, command) -> None:
        self.commands.append(command)


@pytest.fixture
def device() -> FakeDevice:
    return FakeDevice()
