"""Services for Google Photos Frame."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import selector

from .const import DOMAIN
from .coordinator import GooglePhotosFrameCoordinator

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_SYNC_NOW = "sync_now"
SERVICE_GET_CURRENT_PHOTO = "get_current_photo"
SERVICE_GET_PHOTOS = "get_photos"
SERVICE_NEXT_PHOTO = "next_photo"
SERVICE_PREVIOUS_PHOTO = "previous_photo"
SERVICE_SET_PHOTO = "set_photo"
SERVICE_CLEAR_CACHE = "clear_cache"

# Event name
EVENT_PHOTO_CHANGED = f"{DOMAIN}_photo_changed"

# Schemas
SYNC_NOW_SCHEMA = vol.Schema({})

CLEAR_CACHE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
})

GET_CURRENT_PHOTO_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
})

GET_PHOTOS_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
    vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
    vol.Optional("offset"): vol.All(vol.Coerce(int), vol.Range(min=0)),
})

SET_PHOTO_SCHEMA = vol.Schema({
    vol.Required("entry_id"): str,
    vol.Exclusive("photo_index", "photo_selector"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Exclusive("photo_id", "photo_selector"): str,
})

# Camera target schema for navigation
CAMERA_TARGET_SCHEMA = vol.Schema({
    vol.Required("target"): selector.TargetSelector(
        selector.TargetSelectorConfig(
            entity=[
                selector.EntityFilterSelectorConfig(
                    integration=DOMAIN,
                    domain="camera",
                )
            ]
        )
    ),
})


def _photo_to_dict(photo, hass: HomeAssistant | None = None, entry_id: str | None = None) -> dict[str, Any]:
    """Convert MediaItem to dict with accessible URLs."""
    result = {
        "id": photo.id,
        "filename": photo.filename,
        "width": photo.width,
        "height": photo.height,
        "creation_time": photo.creation_time,
        "local_path": photo.local_path,
    }

    # Add accessible URL via Home Assistant camera proxy
    if hass and entry_id:
        result["url"] = f"/api/camera_proxy/camera.{DOMAIN}_{entry_id}_camera"

    return result


def _fire_photo_changed_event(
    hass: HomeAssistant,
    entry_id: str,
    photo: dict[str, Any],
    photo_index: int,
    total_photos: int,
) -> None:
    """Fire event when photo changes."""
    hass.bus.async_fire(
        EVENT_PHOTO_CHANGED,
        {
            "entry_id": entry_id,
            "photo": photo,
            "photo_index": photo_index,
            "total_photos": total_photos,
        },
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Google Photos Frame."""
    coordinators = hass.data.get(DOMAIN, {})

    def _get_coordinator(entry_id: str | None = None) -> GooglePhotosFrameCoordinator | None:
        """Get coordinator by entry_id or first available."""
        if entry_id:
            return coordinators.get(entry_id)
        if coordinators:
            return next(iter(coordinators.values()))
        return None

    async def handle_sync_now(_call: ServiceCall) -> None:
        """Handle sync_now service - refresh all coordinators."""
        for coord in coordinators.values():
            await coord.async_request_refresh()
        _LOGGER.info("Google Photos Frame sync triggered for %d entries", len(coordinators))

    async def handle_get_current_photo(call: ServiceCall) -> dict:
        """Handle get_current_photo service - return current photo without advancing."""
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(entry_id)

        if not coordinator:
            return {"error": "No configured integrations"}

        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available"}

        photo = coordinator.get_current_photo()
        if not photo:
            return {"error": "No current photo"}

        actual_entry_id = entry_id or next(
            (eid for eid, coord in coordinators.items() if coord is coordinator),
            None
        )

        return {
            "success": True,
            "photo": _photo_to_dict(photo, hass, actual_entry_id),
            "photo_index": coordinator._current_index,
            "total_photos": len(coordinator.data.media_items),
            "order_mode": coordinator.store.order_mode,
            "fill_mode": coordinator.store.fill_mode,
        }

    async def handle_get_photos(call: ServiceCall) -> dict:
        """Handle get_photos service - return list of all photos."""
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(entry_id)

        if not coordinator:
            return {"error": "No configured integrations", "photos": []}

        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available", "photos": []}

        limit = call.data.get("limit", 100)
        offset = call.data.get("offset", 0)

        actual_entry_id = entry_id or next(
            (eid for eid, coord in coordinators.items() if coord is coordinator),
            None
        )

        items = coordinator.data.media_items[offset : offset + limit]
        photos = [_photo_to_dict(p, hass, actual_entry_id) for p in items]

        return {
            "success": True,
            "photos": photos,
            "total_photos": len(coordinator.data.media_items),
            "returned_count": len(photos),
            "offset": offset,
            "album_name": coordinator.data.album_name,
            "last_sync": coordinator.data.last_sync,
        }

    async def handle_next_photo(call: ServiceCall) -> dict:
        """Handle next_photo service - advance to next photo and return it."""
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(entry_id)

        if not coordinator:
            return {"error": "No configured integrations"}

        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available"}

        photo = await coordinator.async_next_photo()
        if not photo:
            return {"error": "Failed to get next photo"}

        actual_entry_id = entry_id or next(
            (eid for eid, coord in coordinators.items() if coord is coordinator),
            None
        )

        photo_dict = _photo_to_dict(photo, hass, actual_entry_id)

        # Fire event
        if actual_entry_id:
            _fire_photo_changed_event(
                hass,
                actual_entry_id,
                photo_dict,
                coordinator._current_index,
                len(coordinator.data.media_items),
            )

        return {
            "success": True,
            "photo": photo_dict,
            "photo_index": coordinator._current_index,
            "total_photos": len(coordinator.data.media_items),
        }

    async def handle_previous_photo(call: ServiceCall) -> dict:
        """Handle previous_photo service - go to previous photo and return it."""
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(entry_id)

        if not coordinator:
            return {"error": "No configured integrations"}

        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available"}

        photo = await coordinator.async_previous_photo()
        if not photo:
            return {"error": "Failed to get previous photo"}

        actual_entry_id = entry_id or next(
            (eid for eid, coord in coordinators.items() if coord is coordinator),
            None
        )

        photo_dict = _photo_to_dict(photo, hass, actual_entry_id)

        # Fire event
        if actual_entry_id:
            _fire_photo_changed_event(
                hass,
                actual_entry_id,
                photo_dict,
                coordinator._current_index,
                len(coordinator.data.media_items),
            )

        return {
            "success": True,
            "photo": photo_dict,
            "photo_index": coordinator._current_index,
            "total_photos": len(coordinator.data.media_items),
        }

    async def handle_set_photo(call: ServiceCall) -> dict:
        """Handle set_photo service - jump to specific photo by index or ID."""
        entry_id = call.data.get("entry_id")
        coordinator = _get_coordinator(entry_id)

        if not coordinator:
            return {"error": "Integration not found"}

        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available"}

        photo_index = call.data.get("photo_index")
        photo_id = call.data.get("photo_id")

        if photo_index is not None:
            if photo_index >= len(coordinator.data.media_items):
                return {"error": f"Index {photo_index} out of range (0-{len(coordinator.data.media_items) - 1})"}
            coordinator._current_index = photo_index
        elif photo_id is not None:
            for idx, item in enumerate(coordinator.data.media_items):
                if item.id == photo_id:
                    coordinator._current_index = idx
                    break
            else:
                return {"error": f"Photo ID not found: {photo_id}"}

        photo = coordinator.get_current_photo()
        if not photo:
            return {"error": "Failed to get photo"}

        actual_entry_id = entry_id or next(
            (eid for eid, coord in coordinators.items() if coord is coordinator),
            None
        )

        photo_dict = _photo_to_dict(photo, hass, actual_entry_id)

        # Fire event
        if actual_entry_id:
            _fire_photo_changed_event(
                hass,
                actual_entry_id,
                photo_dict,
                coordinator._current_index,
                len(coordinator.data.media_items),
            )

        return {
            "success": True,
            "photo": photo_dict,
            "photo_index": coordinator._current_index,
            "total_photos": len(coordinator.data.media_items),
        }

    async def handle_clear_cache(call: ServiceCall) -> dict:
        """Handle clear_cache service - clear cached photos."""
        entry_id = call.data.get("entry_id")

        if entry_id:
            if entry_id in coordinators:
                await coordinators[entry_id].async_clear_cache()
                _LOGGER.info("Cleared cache for entry %s", entry_id)
                return {"success": True, "entry_id": entry_id}
            return {"error": f"Entry {entry_id} not found"}

        # Clear all
        cleared = []
        for eid, coord in coordinators.items():
            await coord.async_clear_cache()
            cleared.append(eid)
            _LOGGER.info("Cleared cache for entry %s", eid)

        return {"success": True, "cleared_entries": cleared}

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_NOW,
        handle_sync_now,
        schema=SYNC_NOW_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CURRENT_PHOTO,
        handle_get_current_photo,
        schema=GET_CURRENT_PHOTO_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PHOTOS,
        handle_get_photos,
        schema=GET_PHOTOS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_NEXT_PHOTO,
        handle_next_photo,
        schema=GET_CURRENT_PHOTO_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVIOUS_PHOTO,
        handle_previous_photo,
        schema=GET_CURRENT_PHOTO_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PHOTO,
        handle_set_photo,
        schema=SET_PHOTO_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        handle_clear_cache,
        schema=CLEAR_CACHE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services when integration is removed."""
    hass.services.async_unregister(DOMAIN, SERVICE_SYNC_NOW)
    hass.services.async_unregister(DOMAIN, SERVICE_GET_CURRENT_PHOTO)
    hass.services.async_unregister(DOMAIN, SERVICE_GET_PHOTOS)
    hass.services.async_unregister(DOMAIN, SERVICE_NEXT_PHOTO)
    hass.services.async_unregister(DOMAIN, SERVICE_PREVIOUS_PHOTO)
    hass.services.async_unregister(DOMAIN, SERVICE_SET_PHOTO)
    hass.services.async_unregister(DOMAIN, SERVICE_CLEAR_CACHE)
    _LOGGER.info("Unregistered Google Photos Frame services")
