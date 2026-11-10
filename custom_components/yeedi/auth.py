"""Yeedi authentication on top of deebot-client.

Yeedi is an Ecovacs brand: the portal (ecouser.net) and the MQTT broker are shared with
Ecovacs, only the login step differs (yeedi.com domain, Yeedi app keys, app code
``yd_global_e`` and organisation ``ECOYDWW``). Values come from ecovacs-deebot.js
(``library/constants.js`` and ``index.js``), the Node library that supports Yeedi.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

from deebot_client import authentication as _auth
from deebot_client.authentication import (
    Authenticator,
    RestConfiguration,
    _AuthClient,  # noqa: PLC2701
    create_rest_config as _create_rest_config,
)
from deebot_client.const import COUNTRY_CHINA, PATH_API_USERS_USER, REALM
from deebot_client.exceptions import AuthenticationError
from deebot_client.models import AccountCredentials

YEEDI_CLIENT_KEY = "1581917520081"
YEEDI_CLIENT_SECRET = "ed5b3dd9a0253de7d90305d077eb5fee"  # noqa: S105
YEEDI_AUTH_CLIENT_KEY = "1581923437995"
YEEDI_AUTH_CLIENT_SECRET = "304a71592690995b2bb304e66b5ddee6"  # noqa: S105
YEEDI_META = {"appCode": "yd_global_e", "appVersion": "1.3.0"}

_PRIVATE_API_PATH_FORMAT = _auth._PRIVATE_API_PATH_FORMAT  # noqa: SLF001
_GLOBAL_AUTHCODE_PATH = _auth._GLOBAL_AUTHCODE_PATH  # noqa: SLF001


def create_yeedi_rest_config(
    session: Any,
    *,
    device_id: str,
    alpha_2_country: str,
    override_rest_url: str | None = None,
) -> RestConfiguration:
    """Create the REST configuration with the Yeedi login endpoints."""
    cfg = _create_rest_config(
        session,
        device_id=device_id,
        alpha_2_country=alpha_2_country,
        override_rest_url=override_rest_url,
    )
    if override_rest_url:
        return cfg
    return RestConfiguration(
        session=cfg.session,
        device_id=cfg.device_id,
        country=cfg.country,
        portal_url=cfg.portal_url,
        login_url=cfg.login_url.replace("ecovacs.", "yeedi."),
        auth_code_url=cfg.auth_code_url.replace("ecovacs.", "yeedi."),
    )


class YeediAuthClient(_AuthClient):
    """Auth client using the Yeedi application identity."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._meta = {**self._meta, **YEEDI_META}

    # The methods below override the name-mangled private methods of _AuthClient.

    async def _AuthClient__call_private_api(  # noqa: N802
        self, endpoint: str, params: dict[str, str | int]
    ) -> Any:
        url = urljoin(
            self._config.login_url,
            _PRIVATE_API_PATH_FORMAT.format(endpoint=endpoint, **self._meta),
        )
        return await self._AuthClient__do_auth_response(
            url,
            self._AuthClient__sign(
                {**params, **self._AuthClient__request_metadata()},
                self._meta,
                YEEDI_CLIENT_KEY,
                YEEDI_CLIENT_SECRET,
            ),
        )

    async def _AuthClient__call_auth_api(  # noqa: N802
        self, access_token: str, user_id: str
    ) -> str:
        params: dict[str, str | int] = {
            "uid": user_id,
            "accessToken": access_token,
            "bizType": "ECOVACS_IOT",
            "deviceId": self._meta["deviceId"],
            "authTimespan": int(time.time() * 1000),
        }
        url = urljoin(self._config.auth_code_url, _GLOBAL_AUTHCODE_PATH)
        response = await self._AuthClient__do_auth_response(
            url,
            self._AuthClient__sign(
                params,
                {"openId": "global"},
                YEEDI_AUTH_CLIENT_KEY,
                YEEDI_AUTH_CLIENT_SECRET,
            ),
        )
        res = self._AuthClient__expect_dict(response, "Invalid auth code response")
        return str(res["authCode"])

    async def _AuthClient__call_login_by_it_token(  # noqa: N802
        self, user_id: str, auth_code: str
    ) -> dict[str, str]:
        china = self._config.country == COUNTRY_CHINA
        data = {
            "edition": "ECOGLOBLE",
            "userId": user_id,
            "token": auth_code,
            "realm": REALM,
            "resource": self._config.device_id,
            "org": "ECOYDCN" if china else "ECOYDWW",
            "last": "",
            "country": "Chinese" if china else self._config.country,
            "todo": "loginByItToken",
        }
        for i in range(3):
            resp = await self.post(PATH_API_USERS_USER, data)
            if resp["result"] == "ok":
                return resp
            if resp["result"] == "fail" and resp["error"] == "set token error.":
                _auth._LOGGER.warning(  # noqa: SLF001
                    "loginByItToken set token error, attempt %d/3", i + 2
                )
                continue
            msg = f"failure {resp['error']} ({resp['errno']}) for call {PATH_API_USERS_USER}"
            raise AuthenticationError(msg)
        raise AuthenticationError("failed to login with token")


class YeediAuthenticator(Authenticator):
    """Authenticator that logs in through the Yeedi endpoints."""

    def __init__(
        self,
        config: RestConfiguration,
        account_id: str,
        password_hash: str,
        *,
        account_credentials: AccountCredentials | None = None,
    ) -> None:
        super().__init__(
            config,
            account_id,
            password_hash,
            account_credentials=account_credentials,
        )
        self._auth_client = YeediAuthClient(
            config,
            account_id,
            password_hash,
            on_account_credentials=self._set_account_credentials,
        )
