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

PLATFORMS = [
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

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
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once for first entry)
    loaded_entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if len(loaded_entries) == 1:
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
        # Unregister services when last entry is removed
        loaded_entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not loaded_entries:
            from .services import async_unload_services
            await async_unload_services(hass)

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: GooglePhotosFrameConfigEntry
) -> None:
    """Handle removal of a config entry."""
    # Clean up any persistent store data
    from pathlib import Path
    store_path = Path(hass.config.path(".storage", f"{DOMAIN}_{entry.entry_id}"))
    if store_path.exists():
        try:
            store_path.unlink()
            _LOGGER.info("Removed store data for entry %s", entry.entry_id)
        except OSError as err:
            _LOGGER.warning("Failed to remove store data: %s", err)


async def async_migrate_entry(
    hass: HomeAssistant, entry: GooglePhotosFrameConfigEntry
) -> bool:
    """Migrate old entry data to new version."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Future migrations will go here
        hass.config_entries.async_update_entry(entry, version=1)

    _LOGGER.debug("Migration to version %s successful", entry.version)
    return True
