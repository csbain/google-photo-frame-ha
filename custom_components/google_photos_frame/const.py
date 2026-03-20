"""Constants for the Google Photos Frame integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "google_photos_frame"

# Configuration keys
CONF_ALBUM_NAME: Final = "album_name"
CONF_ALBUM_ID: Final = "album_id"
CONF_SYNC_INTERVAL: Final = "sync_interval"
CONF_MAX_PHOTOS: Final = "max_photos"
CONF_DOWNLOAD_QUALITY: Final = "download_quality"
CONF_DISPLAY_INTERVAL: Final = "display_interval"
CONF_SHUFFLE_MODE: Final = "shuffle_mode"

# Defaults
DEFAULT_ALBUM_NAME: Final = "Home Assistant Photo Frame"
DEFAULT_SYNC_INTERVAL: Final = 5  # minutes
DEFAULT_MAX_PHOTOS: Final = 100
DEFAULT_DOWNLOAD_QUALITY: Final = "full"
DEFAULT_DISPLAY_INTERVAL: Final = 30  # seconds
DEFAULT_SHUFFLE_MODE: Final = True

# Storage paths
STORAGE_DIR: Final = "google_photos_frame"
MEDIA_INDEX_FILE: Final = "media_index.json"
CACHE_INDEX_FILE: Final = "cache_index.json"
PHOTOS_DIR: Final = "photos"
CACHE_DIR: Final = "cache"

# Quality options
QUALITY_FULL: Final = "full"
QUALITY_THUMBNAIL: Final = "thumbnail"


class FillMode(StrEnum):
    """Image fill mode options."""

    COVER = "cover"
    CONTAIN = "contain"
    BLUR = "blur"


class OrderMode(StrEnum):
    """Photo ordering options."""

    ALBUM = "album_order"
    RANDOM = "random"


DEFAULT_FILL_MODE: Final = FillMode.BLUR
DEFAULT_ORDER_MODE: Final = OrderMode.RANDOM

# Aspect ratios
ASPECT_RATIOS: Final = ["16:9", "16:10", "4:3", "1:1", "3:4", "10:16", "9:16"]
DEFAULT_ASPECT_RATIO: Final = "16:9"

# Cache settings
CACHE_STALE_DAYS: Final = 7  # Days before unused resolution cache is removed
CACHE_DOWNLOAD_MINUTES: Final = 10  # Minutes before re-downloading image
CACHE_MAX_ITEMS: Final = 120  # Max items in download cache

# Shuffle settings
SHUFFLE_HISTORY_SIZE: Final = 20  # Number of recent photos to avoid repeating
