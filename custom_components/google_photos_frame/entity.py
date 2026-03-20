"""Base entity class for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GooglePhotosFrameCoordinator

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry


class GooglePhotosFrameEntity(CoordinatorEntity[GooglePhotosFrameCoordinator], Entity):
    """Base entity for Google Photos Frame."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entry = entry

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
