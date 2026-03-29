"""DataUpdateCoordinator for Google Photos Frame."""

from __future__ import annotations

import hashlib
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GooglePhotosFrameClient
from .issue_handler import async_create_auth_issue, async_delete_auth_issue
from .cache_manager import CacheManager
from .models import AlbumData, MediaItem
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
    SHUFFLE_HISTORY_SIZE,
    STORAGE_DIR,
)
from .store import SettingsStore

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry

_LOGGER = logging.getLogger(__name__)


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

        # Runtime settings store
        self.store = SettingsStore(entry=entry)

        # Cache manager for resolution-based caching
        self.cache_manager = CacheManager(hass, entry)

        # Photo navigation state
        self._current_index: int = 0
        self._shuffle_history: list[str] = []

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Google Photos Frame",
            update_interval=timedelta(minutes=sync_interval),
        )

    @property
    def update_interval_minutes(self) -> int:
        """Get update interval in minutes."""
        if self.update_interval:
            return int(self.update_interval.total_seconds() / 60)
        return DEFAULT_SYNC_INTERVAL

    @update_interval_minutes.setter
    def update_interval_minutes(self, value: int) -> None:
        """Set update interval in minutes."""
        self.update_interval = timedelta(minutes=value)
        self._schedule_refresh()

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

    async def async_initialize(self) -> None:
        """Initialize coordinator components."""
        await self.cache_manager.async_initialize()

    def clear_cache(self) -> None:
        """Clear all cached photos and index."""
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

        # Clear resolution caches
        self.hass.async_create_task(self.cache_manager.clear_all())

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
            media_index = await self.hass.async_add_executor_job(
                self._load_media_index
            )

            # Process media items
            synced_items: list[MediaItem] = []
            new_index: dict = {}
            new_media_ids: set[str] = set()

            for item in media_items[: self._max_photos]:
                media_id = item["id"]
                media_hash = self._get_hash(media_id)
                new_media_ids.add(media_id)

                # Check if already downloaded
                if media_id in media_index:
                    local_path = media_index[media_id]["local_path"]
                    # Verify file exists
                    if Path(local_path).exists():
                        synced_items.append(
                            MediaItem(
                                id=media_id,
                                filename=item["filename"],
                                local_path=local_path,
                                width=item.get("width"),
                                height=item.get("height"),
                                creation_time=item.get("creation_time"),
                                url=item.get("base_url"),
                            )
                        )
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

                synced_items.append(
                    MediaItem(
                        id=media_id,
                        filename=item["filename"],
                        local_path=local_path,
                        width=item.get("width"),
                        height=item.get("height"),
                        creation_time=item.get("creation_time"),
                        url=item.get("base_url"),
                    )
                )
                new_index[media_id] = {
                    "local_path": local_path,
                    "hash": media_hash,
                }

            # Find removed media IDs
            old_media_ids = set(media_index.keys())
            removed_ids = list(old_media_ids - new_media_ids)

            # Clean up orphaned files and cache entries
            await self.hass.async_add_executor_job(
                self._cleanup_orphans, new_index
            )

            # Remove from cache manager
            if removed_ids:
                await self.cache_manager.remove_media(removed_ids)
                _LOGGER.info("Removed %d photos from cache", len(removed_ids))

            # Save updated index
            await self.hass.async_add_executor_job(
                self._save_media_index, new_index
            )

            # Queue background processing for new items
            await self.cache_manager.queue_background_processing(synced_items)

            # Clear any existing auth issue on successful sync
            async_delete_auth_issue(self.hass, self._entry.entry_id)

            return AlbumData(
                album_id=album_id,
                album_name=self._entry.data.get("album_name", "Photo Frame"),
                media_items=synced_items,
                last_sync=datetime.now(timezone.utc).isoformat(),
                media_count=len(synced_items),
            )

        except ConfigEntryAuthFailed as err:
            # Create repair issue for auth failure
            async_create_auth_issue(self.hass, self._entry.entry_id)
            raise
        except Exception as err:
            if "401" in str(err) or "unauthorized" in str(err).lower():
                async_create_auth_issue(self.hass, self._entry.entry_id)
                raise ConfigEntryAuthFailed(f"Authentication expired: {err}") from err
            # Clear any existing auth issue on successful update path
            async_delete_auth_issue(self.hass, self._entry.entry_id)
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

    def _select_random_photo(self) -> MediaItem | None:
        """Select a random photo avoiding recent history."""
        if not self.data or not self.data.media_items:
            return None

        items = self.data.media_items
        available_ids = {item.id for item in items}

        # Clean up history for items no longer in album
        self._shuffle_history = [
            hid for hid in self._shuffle_history if hid in available_ids
        ]

        # Get candidates not in recent history
        candidates = [item for item in items if item.id not in self._shuffle_history]

        # If all photos are in history, reset history
        if not candidates:
            self._shuffle_history.clear()
            candidates = items

        # Select random photo
        selected = random.choice(candidates)

        # Add to history
        self._shuffle_history.append(selected.id)
        if len(self._shuffle_history) > SHUFFLE_HISTORY_SIZE:
            self._shuffle_history.pop(0)

        self._current_index = items.index(selected)
        return selected

    async def async_next_photo(self) -> MediaItem | None:
        """Advance to next photo based on order mode."""
        if not self.data or not self.data.media_items:
            return None

        items = self.data.media_items

        if self.store.order_mode == "random":
            return self._select_random_photo()

        # Sequential order
        self._current_index += 1
        if self._current_index >= len(items):
            self._current_index = 0

        return items[self._current_index]

    async def async_previous_photo(self) -> MediaItem | None:
        """Go to previous photo based on order mode."""
        if not self.data or not self.data.media_items:
            return None

        items = self.data.media_items

        if self.store.order_mode == "random":
            # In random mode, just select another random photo
            return self._select_random_photo()

        # Sequential order
        self._current_index -= 1
        if self._current_index < 0:
            self._current_index = len(items) - 1

        return items[self._current_index]

    def get_current_photo(self) -> MediaItem | None:
        """Get the current photo."""
        if not self.data or not self.data.media_items:
            return None

        if self._current_index < 0 or self._current_index >= len(
            self.data.media_items
        ):
            self._current_index = 0

        return self.data.media_items[self._current_index]
