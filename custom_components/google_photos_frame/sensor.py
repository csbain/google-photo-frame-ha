"""Sensor platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GooglePhotosFrameCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import GooglePhotosFrameConfigEntry

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="album",
        translation_key="album",
        icon="mdi:image-multiple",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Photos Frame sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities([GooglePhotosAlbumSensor(coordinator, entry)])


class GooglePhotosAlbumSensor(SensorEntity):
    """Sensor for album info."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
    ) -> None:
        """Initialize sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_album"
        self.entity_description = SENSOR_DESCRIPTIONS[0]

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

    @property
    def native_value(self) -> str | None:
        """Return the album name."""
        if self.coordinator.data:
            return self.coordinator.data.album_name
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}

        return {
            "media_count": self.coordinator.data.media_count,
            "last_sync": self.coordinator.data.last_sync,
            "album_id": self.coordinator.data.album_id,
        }
