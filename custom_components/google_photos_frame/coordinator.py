"""DataUpdateCoordinator for Google Photos Frame."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GooglePhotosFrameClient
from .const import (
    CONF_ALBUM_ID,
    CONF_MAX_PHOTOS,
    CONF_SYNC_INTERVAL,
    DEFAULT_MAX_PHOTOS,
    DEFAULT_SYNC_INTERVAL,
    MEDIA_INDEX_FILE,
    PHOTOS_DIR,
    QUALITY_FULL,
    QUALITY_THUMBNAIL,
    STORAGE_DIR,
)

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class MediaItem:
    """Represents a synced media item."""
    id: str
    filename: str
    local_path: str
    width: int | None
    height: int | None
    creation_time: str | None


@dataclass
class AlbumData:
    """Data stored by the coordinator."""
    album_id: str
    album_name: str
    media_items: list[MediaItem] = field(default_factory=list)
    last_sync: str | None = None
    media_count: int = 0


class GooglePhotosFrameCoordinator(DataUpdateCoordinator[AlbumData]):
    """Coordinator for syncing Google Photos album."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GooglePhotosFrameConfigEntry,
        client: GooglePhotosFrameClient,
    ) -> None:
        """Initialize coordinator."""
        self._client = client
        self._entry = entry
        self._storage_path = Path(hass.config.path(STORAGE_DIR))
        self._photos_path = self._storage_path / PHOTOS_DIR

        # Ensure storage directories exist
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._photos_path.mkdir(parents=True, exist_ok=True)

        sync_interval = entry.options.get(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL)
        max_photos = entry.options.get(CONF_MAX_PHOTOS, DEFAULT_MAX_PHOTOS)
        self._max_photos = max_photos

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Google Photos Frame",
            update_interval=timedelta(minutes=sync_interval),
        )

    def _get_media_index_path(self) -> Path:
        """Get path to media index file."""
        return self._storage_path / MEDIA_INDEX_FILE

    def _get_photos_path(self) -> Path:
        """Get path to photos directory."""
        return self._photos_path

    def _get_hash(self, media_id: str) -> str:
        """Generate hash for media ID."""
        return hashlib.sha256(media_id.encode()).hexdigest()[:16]

    def _load_media_index(self) -> dict:
        """Load media index from disk."""
        index_path = self._get_media_index_path()
        if index_path.exists():
            try:
                with open(index_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as err:
                _LOGGER.warning("Failed to load media index: %s", err)
        return {}

    def _save_media_index(self, index: dict) -> None:
        """Save media index to disk."""
        index_path = self._get_media_index_path()
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

    def clear_cache(self) -> None:
        """Clear all cached photos and index."""
        import shutil

        # Clear photos directory
        if self._photos_path.exists():
            for file_path in self._photos_path.glob("*"):
                try:
                    file_path.unlink()
                    _LOGGER.debug("Removed cached photo: %s", file_path)
                except OSError as err:
                    _LOGGER.warning("Failed to remove %s: %s", file_path, err)

        # Clear index file
        index_path = self._get_media_index_path()
        if index_path.exists():
            try:
                index_path.unlink()
                _LOGGER.debug("Removed media index")
            except OSError as err:
                _LOGGER.warning("Failed to remove index: %s", err)

        _LOGGER.info("Cleared Google Photos Frame cache")

    async def async_clear_cache(self) -> None:
        """Clear cache asynchronously."""
        await self.hass.async_add_executor_job(self.clear_cache)

    async def _async_update_data(self) -> AlbumData:
        """Fetch data from Google Photos API."""
        try:
            album_id = self._entry.data.get(CONF_ALBUM_ID)
            if not album_id:
                raise UpdateFailed("No album configured")

            # Fetch album media
            media_items = await self._client.async_get_album_media(album_id)

            # Load existing index
            media_index = self._load_media_index()

            # Process media items
            synced_items: list[MediaItem] = []
            new_index: dict = {}

            for item in media_items[:self._max_photos]:
                media_id = item["id"]
                media_hash = self._get_hash(media_id)

                # Check if already downloaded
                if media_id in media_index:
                    local_path = media_index[media_id]["local_path"]
                    # Verify file exists
                    if Path(local_path).exists():
                        synced_items.append(MediaItem(
                            id=media_id,
                            filename=item["filename"],
                            local_path=local_path,
                            width=item["width"],
                            height=item["height"],
                            creation_time=item["creation_time"],
                        ))
                        new_index[media_id] = media_index[media_id]
                        continue

                # Download new media
                quality = self._entry.options.get("download_quality", QUALITY_FULL)
                if quality == QUALITY_THUMBNAIL:
                    content = await self._client.async_download_media(
                        item["base_url"], media_id, width=300, height=300
                    )
                    ext = "_thumb.jpg"
                else:
                    content = await self._client.async_download_media(
                        item["base_url"], media_id
                    )
                    ext = "_full.jpg"

                local_path = str(self._photos_path / f"{media_hash}{ext}")
                await self.hass.async_add_executor_job(
                    self._write_file, local_path, content
                )

                synced_items.append(MediaItem(
                    id=media_id,
                    filename=item["filename"],
                    local_path=local_path,
                    width=item["width"],
                    height=item["height"],
                    creation_time=item["creation_time"],
                ))
                new_index[media_id] = {
                    "local_path": local_path,
                    "hash": media_hash,
                }

            # Save updated index
            self._save_media_index(new_index)

            # Clean up orphaned files
            self._cleanup_orphans(new_index)

            return AlbumData(
                album_id=album_id,
                album_name=self._entry.data.get("album_name", "Photo Frame"),
                media_items=synced_items,
                last_sync=datetime.now().isoformat(),
                media_count=len(synced_items),
            )

        except Exception as err:
            if "401" in str(err) or "unauthorized" in str(err).lower():
                raise ConfigEntryAuthFailed(f"Authentication expired: {err}") from err
            raise UpdateFailed(f"Error syncing album: {err}") from err

    def _write_file(self, path: str, content: bytes) -> None:
        """Write content to file (sync)."""
        with open(path, "wb") as f:
            f.write(content)

    def _cleanup_orphans(self, current_index: dict) -> None:
        """Remove files not in current index."""
        current_paths = {v["local_path"] for v in current_index.values()}
        for file_path in self._photos_path.glob("*"):
            if str(file_path) not in current_paths:
                try:
                    file_path.unlink()
                    _LOGGER.debug("Removed orphaned file: %s", file_path)
                except OSError as err:
                    _LOGGER.warning("Failed to remove orphan %s: %s", file_path, err)
