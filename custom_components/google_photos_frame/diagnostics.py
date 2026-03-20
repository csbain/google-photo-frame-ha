"""Diagnostics support for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: GooglePhotosFrameConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    diagnostics: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "store": coordinator.store.to_dict() if coordinator.store else None,
    }

    if coordinator.data:
        data = coordinator.data
        diagnostics["album"] = {
            "album_id": data.album_id,
            "album_name": data.album_name,
            "media_count": data.media_count,
            "last_sync": data.last_sync,
            "total_photos": len(data.media_items) if data.media_items else 0,
        }

        # Include sample photo info (first 3, without local paths)
        if data.media_items:
            diagnostics["sample_photos"] = [
                {
                    "id": photo.id[:8] + "...",  # Truncated for privacy
                    "filename": photo.filename,
                    "width": photo.width,
                    "height": photo.height,
                    "creation_time": photo.creation_time,
                }
                for photo in data.media_items[:3]
            ]

    # Coordinator state
    diagnostics["coordinator"] = {
        "last_update_success": coordinator.last_update_success,
        "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
        "update_interval_minutes": coordinator.update_interval_minutes,
        "current_index": coordinator._current_index,
    }

    return diagnostics
