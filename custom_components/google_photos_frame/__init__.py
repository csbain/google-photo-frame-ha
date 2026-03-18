"""The Google Photos Frame integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .api import GooglePhotosFrameClient
from .const import DOMAIN
from .coordinator import GooglePhotosFrameCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CAMERA, Platform.SENSOR]

type GooglePhotosFrameConfigEntry = ConfigEntry[GooglePhotosFrameCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GooglePhotosFrameConfigEntry
) -> bool:
    """Set up Google Photos Frame from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    client = GooglePhotosFrameClient(hass, session)

    coordinator = GooglePhotosFrameCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Store coordinator for platform access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once)
    if len(hass.data[DOMAIN]) == 1:
        from .services import async_setup_services
        await async_setup_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GooglePhotosFrameConfigEntry
) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data

    # Clear cache when unloading (album removed/not selected)
    if coordinator:
        await coordinator.async_clear_cache()
        _LOGGER.info("Cleared cache for unloaded entry %s", entry.entry_id)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
