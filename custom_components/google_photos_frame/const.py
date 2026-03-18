"""Constants for the Google Photos Frame integration."""

DOMAIN = "google_photos_frame"

# Configuration
CONF_ALBUM_NAME = "album_name"
CONF_ALBUM_ID = "album_id"
CONF_SYNC_INTERVAL = "sync_interval"
CONF_MAX_PHOTOS = "max_photos"
CONF_DOWNLOAD_QUALITY = "download_quality"
CONF_DISPLAY_INTERVAL = "display_interval"
CONF_SHUFFLE_MODE = "shuffle_mode"

# Defaults
DEFAULT_ALBUM_NAME = "Home Assistant Photo Frame"
DEFAULT_SYNC_INTERVAL = 5  # minutes
DEFAULT_MAX_PHOTOS = 100
DEFAULT_DOWNLOAD_QUALITY = "full"
DEFAULT_DISPLAY_INTERVAL = 30  # seconds
DEFAULT_SHUFFLE_MODE = True

# Storage paths
STORAGE_DIR = "google_photos_frame"
MEDIA_INDEX_FILE = "media_index.json"
PHOTOS_DIR = "photos"

# Quality options
QUALITY_FULL = "full"
QUALITY_THUMBNAIL = "thumbnail"
