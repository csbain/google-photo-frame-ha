"""Config flow for Google Photos Frame integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CONF_ALBUM_ID,
    CONF_ALBUM_NAME,
    CONF_DISPLAY_INTERVAL,
    CONF_MAX_PHOTOS,
    CONF_SHUFFLE_MODE,
    CONF_SYNC_INTERVAL,
    DEFAULT_ALBUM_NAME,
    DEFAULT_DISPLAY_INTERVAL,
    DEFAULT_MAX_PHOTOS,
    DEFAULT_SHUFFLE_MODE,
    DEFAULT_SYNC_INTERVAL,
    DOMAIN,
    OAUTH2_SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Config flow for Google Photos Frame using OAuth2."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH2_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    def __init__(self) -> None:
        """Initialize flow."""
        self._albums: list[tuple[str, str]] = []  # (id, title)
        self.token_data: dict[str, Any] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create entry from OAuth2 flow."""
        # Store the OAuth token data for use in album step
        self.token_data = data

        # Proceed to album selection
        return await self.async_step_album()

    def _get_api_client(self):
        """Get API client for config flow using token data."""
        import aiohttp
        from .api import GooglePhotosFrameClient

        # Get token data - either from initial setup or reconfigure
        token_data = self.token_data
        if not token_data:
            # Try to get from reconfigure entry
            try:
                entry_id = self._get_reconfigure_entry_id()
                entry = self.hass.config_entries.async_get_entry(entry_id)
                if entry:
                    token_data = entry.data
            except (AttributeError, TypeError):
                pass

        if not token_data:
            raise ValueError("No token data available")

        # Create an aiohttp session with auth headers for config flow
        class ConfigFlowOAuth2Session(aiohttp.ClientSession):
            """OAuth2 session for config flow with auth headers."""

            def __init__(self, token: dict, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self._token = token

            @property
            def token(self) -> dict:
                return self._token

            async def async_ensure_token_valid(self) -> bool:
                """Token is fresh during config flow."""
                return True

            def _add_auth_header(self, kwargs: dict) -> None:
                """Add authorization header to request kwargs."""
                headers = kwargs.setdefault("headers", {})
                if "Authorization" not in headers:
                    headers["Authorization"] = f"Bearer {self._token['access_token']}"

            async def get(self, url, **kwargs):
                self._add_auth_header(kwargs)
                return await super().get(url, **kwargs)

            async def post(self, url, **kwargs):
                self._add_auth_header(kwargs)
                return await super().post(url, **kwargs)

        session = ConfigFlowOAuth2Session(token_data)
        return GooglePhotosFrameClient(self.hass, session)

    async def _fetch_albums(self) -> None:
        """Fetch available albums."""
        try:
            client = self._get_api_client()
            albums = await client.async_get_albums()
            self._albums = [(a["id"], a["title"]) for a in albums]
        except Exception:
            self._albums = []

    async def async_step_album(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle album selection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("create_new"):
                # Create new album
                album_name = user_input.get("album_name", DEFAULT_ALBUM_NAME)
                try:
                    client = self._get_api_client()
                    album = await client.async_create_album(album_name)
                    return self.async_create_entry(
                        title=f"Google Photos Frame ({album_name})",
                        data={
                            **self.token_data,
                            CONF_ALBUM_ID: album["id"],
                            CONF_ALBUM_NAME: album_name,
                        },
                    )
                except Exception:
                    errors["base"] = "cannot_create_album"
            elif user_input.get("album_id"):
                # Select existing album
                album_name = next(
                    (title for aid, title in self._albums if aid == user_input["album_id"]),
                    DEFAULT_ALBUM_NAME
                )
                return self.async_create_entry(
                    title=f"Google Photos Frame ({album_name})",
                    data={
                        **self.token_data,
                        CONF_ALBUM_ID: user_input["album_id"],
                        CONF_ALBUM_NAME: album_name,
                    },
                )
            else:
                errors["base"] = "no_album_selected"

        # Fetch existing albums
        await self._fetch_albums()

        album_options = {aid: title for aid, title in self._albums}

        schema = vol.Schema({
            vol.Optional("album_id"): vol.In(album_options) if album_options else str,
            vol.Optional("create_new", default=True): bool,
            vol.Optional("album_name", default=DEFAULT_ALBUM_NAME): str,
        })

        return self.async_show_form(
            step_id="album",
            data_schema=schema,
            errors=errors,
            description_placeholders={"num_albums": str(len(self._albums))},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration to change album."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input.get("album_id"):
                album_name = next(
                    (title for aid, title in self._albums if aid == user_input["album_id"]),
                    ""
                )
                # Get current entry
                entry = self.hass.config_entries.async_get_entry(
                    self._get_reconfigure_entry_id()
                )
                if entry:
                    new_data = {**entry.data}
                    new_data[CONF_ALBUM_ID] = user_input["album_id"]
                    new_data[CONF_ALBUM_NAME] = album_name
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
            errors["base"] = "no_album_selected"

        # Fetch available albums
        await self._fetch_albums()

        if not self._albums:
            return self.async_abort(reason="no_albums")

        schema = vol.Schema({
            vol.Required("album_id"): vol.In({aid: title for aid, title in self._albums}),
        })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders={"num_albums": str(len(self._albums))},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Google Photos Frame."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options

        schema = vol.Schema({
            vol.Optional(
                CONF_SYNC_INTERVAL,
                default=options.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            vol.Optional(
                CONF_MAX_PHOTOS,
                default=options.get(CONF_MAX_PHOTOS, DEFAULT_MAX_PHOTOS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
            vol.Optional(
                CONF_DISPLAY_INTERVAL,
                default=options.get(CONF_DISPLAY_INTERVAL, DEFAULT_DISPLAY_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
            vol.Optional(
                CONF_SHUFFLE_MODE,
                default=options.get(CONF_SHUFFLE_MODE, DEFAULT_SHUFFLE_MODE),
            ): bool,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
