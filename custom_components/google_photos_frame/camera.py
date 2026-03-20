"""Camera platform for Google Photos Frame."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import Camera
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import GooglePhotosFrameConfigEntry
    from .coordinator import GooglePhotosFrameCoordinator
    from .models import MediaItem

_LOGGER = logging.getLogger(__name__)

# Event fired when photo changes
EVENT_PHOTO_CHANGED = f"{DOMAIN}_photo_changed"


def _parse_aspect_ratio(ratio: str) -> tuple[int, int]:
    """Parse aspect ratio string to width, height."""
    try:
        w, h = ratio.split(":")
        return int(w), int(h)
    except (ValueError, AttributeError):
        return 16, 9


class GooglePhotosFrameCamera(Camera):
    """Camera entity for photo frame display."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
    ) -> None:
        """Initialize camera."""
        super().__init__()
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._current_photo: MediaItem | None = None
        self._last_change_time: float = 0.0

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info for grouping entities."""
        if not self.coordinator.data:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.album_id)},
            name=self.coordinator.data.album_name,
            manufacturer="Google",
            model="Photos Album",
        )

    def _should_change_photo(self) -> bool:
        """Check if it's time to change the photo."""
        # Don't auto-change if paused
        if self.coordinator.store.paused:
            return False
        if self._current_photo is None:
            return True
        elapsed = time.time() - self._last_change_time
        return elapsed >= self.coordinator.store.display_interval

    def _fire_photo_changed_event(self) -> None:
        """Fire event when photo changes."""
        if not self._current_photo or not self.coordinator.data:
            return

        self.hass.bus.async_fire(
            EVENT_PHOTO_CHANGED,
            {
                "entry_id": self._entry.entry_id,
                "entity_id": self.entity_id,
                "photo": {
                    "id": self._current_photo.id,
                    "filename": self._current_photo.filename,
                    "width": self._current_photo.width,
                    "height": self._current_photo.height,
                    "creation_time": self._current_photo.creation_time,
                    "url": f"/api/camera_proxy/{self.entity_id}",
                },
                "photo_index": self.coordinator._current_index,
                "total_photos": len(self.coordinator.data.media_items),
                "album_name": self.coordinator.data.album_name,
            },
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera image with resolution-based processing."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return None

        # Change photo if interval elapsed or no current photo
        if self._should_change_photo():
            previous_photo = self._current_photo
            self._current_photo = await self.coordinator.async_next_photo()
            self._last_change_time = time.time()

            # Fire event only if photo actually changed
            if self._current_photo and self._current_photo != previous_photo:
                self._fire_photo_changed_event()

        if not self._current_photo:
            return None

        # Default resolution if not specified
        if width is None or height is None:
            aspect_w, aspect_h = _parse_aspect_ratio(
                self.coordinator.store.aspect_ratio
            )
            # Use a reasonable default resolution
            width = width or 1920
            height = height or int(width * aspect_h / aspect_w)

        # Get fill mode from store
        fill_mode = self.coordinator.store.fill_mode

        try:
            # Use cache manager for resolution-specific processing
            processed = await self.coordinator.cache_manager.get_processed_image(
                self._current_photo,
                width,
                height,
                fill_mode,
            )
            if processed:
                return processed
        except Exception as err:
            _LOGGER.warning("Failed to process image: %s", err)

        # Fallback: return original file
        try:
            return await self.hass.async_add_executor_job(
                self._read_file, self._current_photo.local_path
            )
        except OSError as err:
            _LOGGER.warning("Failed to read photo: %s", err)
            return None

    async def async_next_photo(self) -> None:
        """Manually advance to next photo."""
        previous_photo = self._current_photo
        self._current_photo = await self.coordinator.async_next_photo()
        self._last_change_time = time.time()

        if self._current_photo and self._current_photo != previous_photo:
            self._fire_photo_changed_event()

    async def async_previous_photo(self) -> None:
        """Manually go to previous photo."""
        previous_photo = self._current_photo
        self._current_photo = await self.coordinator.async_previous_photo()
        self._last_change_time = time.time()

        if self._current_photo and self._current_photo != previous_photo:
            self._fire_photo_changed_event()

    def _read_file(self, path: str) -> bytes:
        """Read file contents synchronously."""
        with open(path, "rb") as f:
            return f.read()

    def _get_adjacent_photo_info(self, offset: int) -> dict[str, Any] | None:
        """Get info about photo at offset from current."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return None

        items = self.coordinator.data.media_items
        current_idx = self.coordinator._current_index
        target_idx = (current_idx + offset) % len(items)
        photo = items[target_idx]

        return {
            "id": photo.id,
            "filename": photo.filename,
            "index": target_idx,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}

        data = self.coordinator.data
        items = data.media_items or []

        attrs: dict[str, Any] = {
            # Album info
            "album_name": data.album_name,
            "album_id": data.album_id,
            "media_count": data.media_count,
            "total_photos": len(items),
            "last_sync": data.last_sync,
            # Current photo info
            "current_photo_id": self._current_photo.id if self._current_photo else None,
            "current_photo_filename": (
                self._current_photo.filename if self._current_photo else None
            ),
            "current_photo_index": self.coordinator._current_index,
            "current_photo_width": self._current_photo.width if self._current_photo else None,
            "current_photo_height": self._current_photo.height if self._current_photo else None,
            "current_photo_creation_time": (
                self._current_photo.creation_time if self._current_photo else None
            ),
            # Access URL for external apps
            "photo_url": f"/api/camera_proxy/{self.entity_id}" if self.entity_id else None,
            # Thumbnail URLs for external apps (multiple sizes)
            "thumbnail_url_small": f"/api/camera_proxy/{self.entity_id}?width=320&height=320" if self.entity_id else None,
            "thumbnail_url_medium": f"/api/camera_proxy/{self.entity_id}?width=640&height=640" if self.entity_id else None,
            "thumbnail_url_large": f"/api/camera_proxy/{self.entity_id}?width=1280&height=1280" if self.entity_id else None,
            # Adjacent photos for navigation
            "next_photo": self._get_adjacent_photo_info(1),
            "previous_photo": self._get_adjacent_photo_info(-1),
            # Timing
            "last_change_time": self._last_change_time,
            "display_interval": self.coordinator.store.display_interval,
            "seconds_until_next": max(
                0,
                self.coordinator.store.display_interval - (time.time() - self._last_change_time)
            ) if self._current_photo else 0,
            # Display settings
            "order_mode": self.coordinator.store.order_mode,
            "shuffle_mode": self.coordinator.store.order_mode == "random",
            "fill_mode": self.coordinator.store.fill_mode,
            "aspect_ratio": self.coordinator.store.aspect_ratio,
            # Sync info
            "update_interval_minutes": self.coordinator.update_interval_minutes,
        }

        return attrs


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities,
) -> None:
    """Set up camera platform."""
    coordinator = entry.runtime_data
    async_add_entities([GooglePhotosFrameCamera(coordinator, entry)])
