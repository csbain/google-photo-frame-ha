"""System health support for Google Photos Frame."""

from __future__ import annotations

from typing import Any

from homeassistant.components.system_health import SystemHealthRegistration
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, registration: SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    registration.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get system health info."""
    coordinators = hass.data.get(DOMAIN, {})
    info: dict[str, Any] = {
        "configured_albums": len(coordinators),
    }

    # Add status for each configured album
    album_status = []
    for entry_id, coordinator in coordinators.items():
        status = {
            "album_name": coordinator.data.album_name if coordinator.data else None,
            "last_sync": coordinator.data.last_sync if coordinator.data else None,
            "media_count": len(coordinator.data.media_items) if coordinator.data and coordinator.data.media_items else 0,
            "last_update_success": coordinator.last_update_success,
        }
        album_status.append(status)

    if album_status:
        info["albums"] = album_status

    return info
