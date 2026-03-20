"""Switch platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GooglePhotosFrameCoordinator
from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry


PAUSE_SWITCH = SwitchEntityDescription(
    key="paused",
    translation_key="paused",
    icon="mdi:pause",
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator = entry.runtime_data
    async_add_entities([GooglePhotosFramePauseSwitch(coordinator, entry, PAUSE_SWITCH)])


class GooglePhotosFramePauseSwitch(GooglePhotosFrameEntity, SwitchEntity):
    """Switch to pause/resume slideshow."""

    entity_description: SwitchEntityDescription
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: GooglePhotosFrameCoordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize pause switch."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if paused."""
        return self.coordinator.store.paused

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:pause" if self.coordinator.store.paused else "mdi:play"

    async def async_turn_on(self, **_: dict) -> None:
        """Pause the slideshow."""
        self.coordinator.store.paused = True
        self.coordinator.store.notify()
        self.async_write_ha_state()

    async def async_turn_off(self, **_: dict) -> None:
        """Resume the slideshow."""
        self.coordinator.store.paused = False
        self.coordinator.store.notify()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
