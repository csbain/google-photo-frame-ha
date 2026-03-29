"""API client wrapper for Google Photos Library API."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from google_photos_library_api.api import GooglePhotosLibraryApi
from google_photos_library_api.auth import AbstractAuth
from google_photos_library_api.model import NewAlbum

from homeassistant.helpers import config_entry_oauth2_flow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Retry constants
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_MAX_DELAY = 30.0
RETRY_JITTER = 0.5


def with_retry(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to retry API calls with exponential backoff."""
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception: Exception = Exception("Unknown error")
        for attempt in range(MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except Exception as err:
                last_exception = err
                if attempt < MAX_RETRIES - 1:
                    # Exponential backoff with jitter
                    delay = min(
                        RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, RETRY_JITTER),
                        RETRY_MAX_DELAY,
                    )
                    _LOGGER.warning(
                        "API call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        MAX_RETRIES,
                        delay,
                        err,
                    )
                    await asyncio.sleep(delay)
        raise last_exception
    return wrapper


class AsyncConfigEntryAuth(AbstractAuth):
    """Auth wrapper for runtime use with OAuth2Session."""

    def __init__(
        self,
        websession: Any,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize."""
        super().__init__(websession)
        self._session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._session.async_ensure_token_valid()
        return str(self._session.token["access_token"])


class AsyncConfigFlowAuth(AbstractAuth):
    """Auth wrapper for config flow with a fixed access token."""

    def __init__(self, websession: Any, access_token: str) -> None:
        """Initialize."""
        super().__init__(websession)
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token


class GooglePhotosFrameClient:
    """Wrapper for Google Photos Library API with error handling."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth: AbstractAuth,
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._auth = auth
        self._api = GooglePhotosLibraryApi(auth)

    @with_retry
    async def async_get_albums(self) -> list[dict]:
        """Get all app-created albums."""
        try:
            result = await self._api.list_albums()
            return [
                {"id": album.id, "title": album.title, "media_count": album.media_items_count or 0}
                for album in result.albums
            ]
        except Exception as err:
            _LOGGER.error("Failed to fetch albums: %s", err)
            raise

    @with_retry
    async def async_create_album(self, title: str) -> dict:
        """Create a new album."""
        try:
            album = await self._api.create_album(NewAlbum(title=title))
            return {"id": album.id, "title": album.title, "media_count": 0}
        except Exception as err:
            _LOGGER.error("Failed to create album: %s", err)
            raise

    @with_retry
    async def async_get_album_media(self, album_id: str) -> list[dict]:
        """Get all media items in an album."""
        try:
            result = await self._api.list_media_items(album_id=album_id)
            items = []
            for item in result.media_items:
                items.append({
                    "id": item.id,
                    "filename": item.filename,
                    "mime_type": item.mime_type,
                    "width": item.media_metadata.width if item.media_metadata else None,
                    "height": item.media_metadata.height if item.media_metadata else None,
                    "creation_time": item.media_metadata.creation_time if item.media_metadata else None,
                    "base_url": item.base_url,
                })
            return items
        except Exception as err:
            _LOGGER.error("Failed to fetch album media: %s", err)
            raise

    @with_retry
    async def async_download_media(
        self,
        base_url: str,
        media_id: str,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        """Download media content."""
        try:
            # Build download URL with optional dimensions
            url = f"{base_url}=d"
            if width or height:
                url = f"{base_url}=w{width or height}-h{height or width}"
            resp = await self._auth.get(url)
            return await resp.read()
        except Exception as err:
            _LOGGER.error("Failed to download media %s: %s", media_id, err)
            raise
