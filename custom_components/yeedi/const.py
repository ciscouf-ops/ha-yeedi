"""Constants for the Yeedi integration."""

from deebot_client.events import LifeSpan

DOMAIN = "yeedi"
MANUFACTURER = "yeedi"

CONF_ACCOUNT_CREDENTIALS = "account_credentials"

SUPPORTED_LIFESPANS = (LifeSpan.BRUSH, LifeSpan.FILTER, LifeSpan.SIDE_BRUSH)
