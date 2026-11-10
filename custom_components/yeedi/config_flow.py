"""Config flow for the Yeedi integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
import logging
import random
import string
from typing import Any

from aiohttp import ClientError
from deebot_client.exceptions import (
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
    MqttError,
)
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5

try:
    import probatio as vol
except ImportError:  # Home Assistant before probatio
    import voluptuous as vol  # type: ignore[no-redef]

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, selector

from .auth import YeediAuthenticator, create_yeedi_rest_config
from .const import CONF_ACCOUNT_CREDENTIALS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _new_device_id() -> str:
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))


class YeediConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Yeedi config flow."""

    VERSION = 1

    _input: dict[str, Any]
    _authenticator: YeediAuthenticator | None = None
    _device_id: str

    async def _async_set_input(self, user_input: dict[str, Any]) -> YeediAuthenticator:
        await self._async_teardown_authenticator()
        self._input = user_input
        self._device_id = user_input.get(CONF_DEVICE_ID) or _new_device_id()
        self._authenticator = YeediAuthenticator(
            create_yeedi_rest_config(
                aiohttp_client.async_get_clientsession(self.hass),
                device_id=self._device_id,
                alpha_2_country=user_input[CONF_COUNTRY],
            ),
            user_input[CONF_USERNAME],
            md5(user_input[CONF_PASSWORD]),
        )
        return self._authenticator

    async def _async_teardown_authenticator(self) -> None:
        if self._authenticator is not None:
            await self._authenticator.teardown()
            self._authenticator = None

    @callback
    def async_remove(self) -> None:
        """Tear down the authenticator when the flow is removed."""
        super().async_remove()
        if self._authenticator is not None:
            self.hass.async_create_background_task(
                self._async_teardown_authenticator(),
                name="yeedi_config_flow_authenticator_teardown",
            )

    async def _async_validate(self, authenticator: YeediAuthenticator) -> dict[str, str]:
        """Try to log in and to reach the MQTT broker."""
        try:
            await authenticator.authenticate()
        except DeviceVerificationRequiredError:
            raise
        except ClientError:
            _LOGGER.debug("Cannot connect", exc_info=True)
            return {"base": "cannot_connect"}
        except InvalidAuthenticationError:
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected exception during login")
            return {"base": "unknown"}

        mqtt_config = await self.hass.async_add_executor_job(
            lambda: create_mqtt_config(
                device_id=self._device_id, country=self._input[CONF_COUNTRY]
            )
        )
        try:
            await MqttClient(mqtt_config, authenticator).verify_config()
        except MqttError:
            _LOGGER.debug("Cannot connect to MQTT", exc_info=True)
            return {"base": "cannot_connect"}
        except InvalidAuthenticationError:
            return {"base": "invalid_auth"}
        except Exception:
            _LOGGER.exception("Unexpected exception during MQTT check")
            return {"base": "unknown"}
        return {}

    def _finish_flow(self) -> ConfigFlowResult:
        self._input[CONF_DEVICE_ID] = self._device_id
        if self._authenticator is not None and (
            account := self._authenticator.account_credentials
        ):
            self._input[CONF_ACCOUNT_CREDENTIALS] = asdict(account)
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self._input
            )
        return self.async_create_entry(title=self._input[CONF_USERNAME], data=self._input)

    def _show_form(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> ConfigFlowResult:
        schema = {
            vol.Required(CONF_USERNAME): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_COUNTRY): selector.CountrySelector(),
        }
        if not user_input:
            user_input = {CONF_COUNTRY: self.hass.config.country}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=vol.Schema(schema), suggested_values=user_input
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Yeedi account."""
        errors: dict[str, str] = {}
        if user_input:
            if self.source != SOURCE_REAUTH:
                self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            if getattr(self, "_input", None) and CONF_DEVICE_ID in self._input:
                user_input.setdefault(CONF_DEVICE_ID, self._input[CONF_DEVICE_ID])
            authenticator = await self._async_set_input(user_input)
            try:
                errors = await self._async_validate(authenticator)
            except DeviceVerificationRequiredError:
                try:
                    await authenticator.request_device_verification_code()
                except Exception:
                    _LOGGER.exception("Cannot request the verification code")
                    errors = {"base": "unknown"}
                else:
                    return await self.async_step_device_verification()
            if not errors:
                return self._finish_flow()
        return self._show_form(user_input, errors)

    async def async_step_device_verification(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter the e-mail verification code Yeedi may ask for."""
        errors: dict[str, str] = {}
        if user_input and self._authenticator is not None:
            try:
                await self._authenticator.verify_device(user_input["verification_code"])
            except InvalidVerificationCodeError:
                errors["verification_code"] = "invalid_verification_code"
            except ClientError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during device verification")
                errors["base"] = "unknown"
            else:
                return self._finish_flow()
        return self.async_show_form(
            step_id="device_verification",
            data_schema=vol.Schema({vol.Required("verification_code"): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Re-authenticate."""
        self._input = dict(entry_data)
        return await self.async_step_user()
