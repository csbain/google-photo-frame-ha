"""Binary sensor platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GooglePhotosFrameCoordinator
from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry


SYNC_SENSOR = BinarySensorEntityDescription(
    key="sync_status",
    translation_key="sync_status",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    icon="mdi:sync",
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities([GooglePhotosFrameSyncSensor(coordinator, entry, SYNC_SENSOR)])


class GooglePhotosFrameSyncSensor(GooglePhotosFrameEntity, BinarySensorEntity):
    """Binary sensor for sync status."""

    entity_description: BinarySensorEntityDescription
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize sync sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if sync is working."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra state attributes."""
        attrs = {
            "last_sync": self.coordinator.data.last_sync if self.coordinator.data else None,
            "last_exception": str(self.coordinator.last_exception)
            if self.coordinator.last_exception
            else None,
        }

        if self.coordinator.data:
            attrs["total_photos"] = len(self.coordinator.data.media_items)
            attrs["album_name"] = self.coordinator.data.album_name

        return attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
