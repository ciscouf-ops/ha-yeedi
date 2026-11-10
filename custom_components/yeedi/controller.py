"""Controller: one Yeedi account, its robots and the shared MQTT connection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from functools import partial
import logging

from deebot_client.api_client import ApiClient
from deebot_client.device import Device
from deebot_client.events import FirmwareEvent, NetworkInfoEvent
from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
)
from deebot_client.models import AccountCredentials
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .auth import YeediAuthenticator, create_yeedi_rest_config
from .const import CONF_ACCOUNT_CREDENTIALS, DOMAIN
from .hardware import register_yeedi_models
from .map_data import YeediMapData
from .suction import YeediSuction

_LOGGER = logging.getLogger(__name__)

type YeediConfigEntry = ConfigEntry[YeediController]


class YeediController:
    """Yeedi controller."""

    def __init__(self, hass: HomeAssistant, entry: YeediConfigEntry) -> None:
        """Initialize controller."""
        self._hass = hass
        self._entry = entry
        config = entry.data
        self._devices: list[Device] = []
        self.map_data: dict[str, YeediMapData] = {}
        self.suction: dict[str, YeediSuction] = {}
        self._unsubscribe_device_events: list[Callable[[], None]] = []
        self._device_id = config[CONF_DEVICE_ID]
        country = config[CONF_COUNTRY]

        register_yeedi_models()

        self._authenticator = YeediAuthenticator(
            create_yeedi_rest_config(
                aiohttp_client.async_get_clientsession(hass),
                device_id=self._device_id,
                alpha_2_country=country,
            ),
            config[CONF_USERNAME],
            md5(config[CONF_PASSWORD]),
            account_credentials=(
                AccountCredentials(**account)
                if (account := config.get(CONF_ACCOUNT_CREDENTIALS))
                else None
            ),
        )
        self._unsubscribe_account_credentials = (
            self._authenticator.subscribe_account_credentials(
                self._async_store_account_credentials
            )
        )
        self._api_client = ApiClient(self._authenticator)
        self._mqtt_config_fn = partial(
            create_mqtt_config, device_id=self._device_id, country=country
        )
        self._mqtt_client: MqttClient | None = None

    async def initialize(self) -> None:
        """Connect to the account and the robots."""
        try:
            devices = await self._api_client.get_devices()
            if devices.mqtt:
                mqtt = await self._get_mqtt_client()
                mqtt_devices = [
                    Device(info, self._authenticator) for info in devices.mqtt
                ]
                async with asyncio.TaskGroup() as tg:

                    async def _init(device: Device) -> None:
                        await device.initialize(mqtt)
                        self._subscribe_device_info_events(device)
                        map_data = YeediMapData(self._hass, device)
                        map_data.start()
                        self.map_data[device.device_info["did"]] = map_data
                        suction = YeediSuction(device)
                        suction.start()
                        self.suction[device.device_info["did"]] = suction
                        self._devices.append(device)

                    for device in mqtt_devices:
                        tg.create_task(_init(device))

            for device_config in devices.xmpp + devices.not_supported:
                _LOGGER.warning(
                    "Robot %s (class %s) is not supported yet. Please open an issue"
                    " with these details: %s",
                    device_config.get("nick") or device_config.get("name"),
                    device_config.get("class"),
                    {k: v for k, v in device_config.items() if k != "did"},
                )
        except DeviceVerificationRequiredError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_verification_required",
            ) from ex
        except InvalidAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from ex
        except DeebotError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="setup_error"
            ) from ex

    async def _async_store_account_credentials(
        self, account: AccountCredentials
    ) -> None:
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_ACCOUNT_CREDENTIALS: asdict(account)},
        )

    def _subscribe_device_info_events(self, device: Device) -> None:
        identifier = (DOMAIN, device.device_info["did"])
        device_registry = dr.async_get(self._hass)

        def device_entry() -> dr.DeviceEntry | None:
            return device_registry.async_get_device_by_identifier(
                identifier, self._entry.entry_id
            )

        async def on_firmware(event: FirmwareEvent) -> None:
            if entry := device_entry():
                device_registry.async_update_device(entry.id, sw_version=event.version)

        async def on_network(event: NetworkInfoEvent) -> None:
            if event.mac and (entry := device_entry()):
                device_registry.async_update_device(
                    entry.id,
                    new_connections={(dr.CONNECTION_NETWORK_MAC, event.mac)},
                )

        self._unsubscribe_device_events.extend(
            (
                device.events.subscribe(FirmwareEvent, on_firmware),
                device.events.subscribe(NetworkInfoEvent, on_network),
            )
        )

    async def teardown(self) -> None:
        """Disconnect everything."""
        self._unsubscribe_account_credentials()
        for unsubscribe in self._unsubscribe_device_events:
            unsubscribe()
        for map_data in self.map_data.values():
            map_data.stop()
        for suction in self.suction.values():
            suction.stop()
        for device in self._devices:
            await device.teardown()
        if self._mqtt_client is not None:
            await self._mqtt_client.disconnect()
        await self._authenticator.teardown()

    async def _get_mqtt_client(self) -> MqttClient:
        if self._mqtt_client is None:
            config = await self._hass.async_add_executor_job(self._mqtt_config_fn)
            mqtt = MqttClient(config, self._authenticator)
            await mqtt.verify_config()
            self._mqtt_client = mqtt
        return self._mqtt_client

    @property
    def devices(self) -> list[Device]:
        """Return the connected robots."""
        return self._devices
