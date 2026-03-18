"""API client wrapper for Google Photos Library API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from google_photos_library_api.api import GooglePhotosLibraryApi

from homeassistant.helpers import config_entry_oauth2_flow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class GooglePhotosFrameClient:
    """Wrapper for Google Photos Library API with error handling."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._session = session
        self._api = GooglePhotosLibraryApi(session)

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

    async def async_create_album(self, title: str) -> dict:
        """Create a new album."""
        try:
            album = await self._api.create_album(title)
            return {"id": album.id, "title": album.title, "media_count": 0}
        except Exception as err:
            _LOGGER.error("Failed to create album: %s", err)
            raise

    async def async_get_album_media(self, album_id: str) -> list[dict]:
        """Get all media items in an album."""
        try:
            result = await self._api.search_media_items(album_id=album_id)
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
            return await self._api.get_media_item_content(url)
        except Exception as err:
            _LOGGER.error("Failed to download media %s: %s", media_id, err)
            raise
