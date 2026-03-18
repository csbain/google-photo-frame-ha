"""Camera platform for Google Photos Frame."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.camera import Camera
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_DISPLAY_INTERVAL,
    CONF_SHUFFLE_MODE,
    DEFAULT_DISPLAY_INTERVAL,
    DEFAULT_SHUFFLE_MODE,
    DOMAIN,
)
from .coordinator import GooglePhotosFrameCoordinator, MediaItem

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry

_LOGGER = logging.getLogger(__name__)


class GooglePhotosFrameCamera(Camera):
    """Camera entity for photo frame display."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
    ) -> None:
        """Initialize camera."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._display_interval = entry.options.get(
            CONF_DISPLAY_INTERVAL, DEFAULT_DISPLAY_INTERVAL
        )
        self._shuffle_mode = entry.options.get(
            CONF_SHUFFLE_MODE, DEFAULT_SHUFFLE_MODE
        )
        self._current_photo: MediaItem | None = None
        self._current_index: int = 0
        self._last_change_time: float = 0.0
        self._entry = entry

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

    def _select_photo(self) -> MediaItem | None:
        """Select the next photo to display."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return None

        items = self.coordinator.data.media_items

        if self._shuffle_mode:
            self._current_photo = random.choice(items)
            self._current_index = items.index(self._current_photo)
        else:
            if self._current_index >= len(items):
                self._current_index = 0
            self._current_photo = items[self._current_index]

        self._last_change_time = time.time()
        return self._current_photo

    def _should_change_photo(self) -> bool:
        """Check if it's time to change the photo."""
        if self._current_photo is None:
            return True
        elapsed = time.time() - self._last_change_time
        return elapsed >= self._display_interval

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera image."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return None

        # Change photo if interval elapsed or no current photo
        if self._should_change_photo():
            self._select_photo()

        if not self._current_photo:
            return None

        try:
            image_data = await self.hass.async_add_executor_job(
                self._read_file, self._current_photo.local_path
            )
        except OSError as err:
            _LOGGER.warning("Failed to read photo: %s", err)
            return None

        return image_data

    def _read_file(self, path: str) -> bytes:
        """Read file contents synchronously."""
        with open(path, "rb") as f:
            return f.read()

    async def async_next_photo(self) -> None:
        """Advance to next photo."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return

        items = self.coordinator.data.media_items

        if self._shuffle_mode:
            self._current_photo = random.choice(items)
            self._current_index = items.index(self._current_photo)
        else:
            self._current_index += 1
            if self._current_index >= len(items):
                self._current_index = 0
            self._current_photo = items[self._current_index]

        self._last_change_time = time.time()

    async def async_previous_photo(self) -> None:
        """Go to previous photo."""
        if not self.coordinator.data or not self.coordinator.data.media_items:
            return

        items = self.coordinator.data.media_items

        if self._shuffle_mode:
            self._current_photo = random.choice(items)
            self._current_index = items.index(self._current_photo)
        else:
            self._current_index -= 1
            if self._current_index < 0:
                self._current_index = len(items) - 1
            self._current_photo = items[self._current_index]

        self._last_change_time = time.time()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}

        return {
            "media_count": self.coordinator.data.media_count,
            "current_photo_filename": (
                self._current_photo.filename if self._current_photo else None
            ),
            "current_photo_index": self._current_index,
            "last_change_time": self._last_change_time,
            "total_photos": len(self.coordinator.data.media_items)
            if self.coordinator.data.media_items
            else 0,
            "shuffle_mode": self._shuffle_mode,
            "display_interval": self._display_interval,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([GooglePhotosFrameCamera(coordinator, entry)])
