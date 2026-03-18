"""Services for Google Photos Frame."""

from __future__ import annotations

import logging
import random

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, selector

from .const import DOMAIN
from .coordinator import GooglePhotosFrameCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SYNC_NOW = "sync_now"
SERVICE_GET_RANDOM_PHOTO = "get_random_photo"
SERVICE_NEXT_PHOTO = "next_photo"
SERVICE_PREVIOUS_PHOTO = "previous_photo"
SERVICE_CLEAR_CACHE = "clear_cache"

# Schema with target selector for camera entity
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

SYNC_NOW_SCHEMA = vol.Schema({})

GET_RANDOM_PHOTO_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.entity_id,
})

CLEAR_CACHE_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): str,
})


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Google Photos Frame."""

    async def handle_sync_now(call: ServiceCall) -> None:
        """Handle sync_now service."""
        for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
            await coordinator.async_request_refresh()
        _LOGGER.info("Google Photos Frame sync triggered")

    async def handle_get_random_photo(call: ServiceCall) -> dict:
        """Handle get_random_photo service."""
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            return {"error": "No configured integrations"}

        coordinator: GooglePhotosFrameCoordinator = coordinators[0]
        if not coordinator.data or not coordinator.data.media_items:
            return {"error": "No photos available"}

        photo = random.choice(coordinator.data.media_items)
        return {
            "id": photo.id,
            "filename": photo.filename,
            "local_path": photo.local_path,
            "width": photo.width,
            "height": photo.height,
            "creation_time": photo.creation_time,
        }

    async def _get_camera_from_target(target: dict) -> tuple | None:
        """Get camera entity from target selector."""
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entity_ids = cv.async_extract_entity_ids(hass, target)

        for entity_id in entity_ids:
            entity = ent_reg.async_get(entity_id)
            if entity and entity.platform == DOMAIN and entity.domain == "camera":
                # Get the config entry for this entity
                config_entry_id = entity.config_entry_id
                if config_entry_id and config_entry_id in hass.data.get(DOMAIN, {}):
                    coordinator = hass.data[DOMAIN][config_entry_id]
                    # Find the camera entity
                    for component in hass.data.get("components", {}).get("camera", []):
                        if hasattr(component, "entity_id") and component.entity_id == entity_id:
                            return component, coordinator
        return None

    async def handle_next_photo(call: ServiceCall) -> None:
        """Handle next_photo service - advance to next photo."""
        target = call.data.get("target", {})
        result = await _get_camera_from_target(target)

        if result is None:
            _LOGGER.warning("No valid camera entity found in target")
            return

        camera, _ = result
        if hasattr(camera, "async_next_photo"):
            await camera.async_next_photo()
            _LOGGER.debug("Advanced to next photo")

    async def handle_previous_photo(call: ServiceCall) -> None:
        """Handle previous_photo service - go to previous photo."""
        target = call.data.get("target", {})
        result = await _get_camera_from_target(target)

        if result is None:
            _LOGGER.warning("No valid camera entity found in target")
            return

        camera, _ = result
        if hasattr(camera, "async_previous_photo"):
            await camera.async_previous_photo()
            _LOGGER.debug("Went to previous photo")

    async def handle_clear_cache(call: ServiceCall) -> None:
        """Handle clear_cache service - clear cached photos."""
        entry_id = call.data.get("entry_id")

        if entry_id:
            # Clear cache for specific entry
            if entry_id in hass.data.get(DOMAIN, {}):
                coordinator = hass.data[DOMAIN][entry_id]
                await coordinator.async_clear_cache()
                _LOGGER.info("Cleared cache for entry %s", entry_id)
            else:
                _LOGGER.warning("Entry %s not found", entry_id)
        else:
            # Clear cache for all entries
            for eid, coordinator in hass.data.get(DOMAIN, {}).items():
                await coordinator.async_clear_cache()
                _LOGGER.info("Cleared cache for entry %s", eid)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_NOW,
        handle_sync_now,
        schema=SYNC_NOW_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_RANDOM_PHOTO,
        handle_get_random_photo,
        schema=GET_RANDOM_PHOTO_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_NEXT_PHOTO,
        handle_next_photo,
        schema=CAMERA_TARGET_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVIOUS_PHOTO,
        handle_previous_photo,
        schema=CAMERA_TARGET_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        handle_clear_cache,
        schema=CLEAR_CACHE_SCHEMA,
    )
