"""Application credentials for Google Photos Frame."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation
from homeassistant.core import HomeAssistant

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

# Google Photos API scope - full access for reading and creating albums
OAUTH2_SCOPE = "https://www.googleapis.com/auth/photoslibrary"


class GooglePhotosOAuth2Implementation(LocalOAuth2Implementation):
    """Custom OAuth2 implementation with Google Photos scope."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": OAUTH2_SCOPE}


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential_id: str
) -> GooglePhotosOAuth2Implementation:
    """Return custom auth implementation with scope."""
    from homeassistant.helpers.application_credentials import (
        async_get_credential,
    )
    from homeassistant.helpers.config_entry_oauth2_flow import (
        async_get_config_entry_implementation,
    )

    credentials = await async_get_credential(hass, auth_domain, credential_id)
    authorization_server = await async_get_authorization_server(hass)

    return GooglePhotosOAuth2Implementation(
        hass,
        auth_domain,
        credentials.client_id,
        credentials.client_secret,
        authorization_server.authorize_url,
        authorization_server.token_url,
    )
