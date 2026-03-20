"""Sensor platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
    """Set up sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            GooglePhotosFrameSensor(coordinator, entry, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class GooglePhotosFrameSensor(GooglePhotosFrameEntity, SensorEntity):
    """Sensor entity for album information."""

    entity_description: SensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

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
