"""Button platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import GooglePhotosFrameConfigEntry


BUTTON_DESCRIPTIONS = [
    ButtonEntityDescription(
        key="next_photo",
        translation_key="next_photo",
        icon="mdi:skip-next",
    ),
    ButtonEntityDescription(
        key="previous_photo",
        translation_key="previous_photo",
        icon="mdi:skip-previous",
    ),
    ButtonEntityDescription(
        key="refresh",
        translation_key="refresh",
        icon="mdi:refresh",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            GooglePhotosFrameButton(coordinator, entry, description)
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class GooglePhotosFrameButton(GooglePhotosFrameEntity, ButtonEntity):
    """Button entity for photo frame controls."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and len(self.coordinator.data.media_items) > 0
        )

    async def async_press(self) -> None:
        """Handle button press."""
        if self.entity_description.key == "next_photo":
            await self.coordinator.async_next_photo()
        elif self.entity_description.key == "previous_photo":
            await self.coordinator.async_previous_photo()
        elif self.entity_description.key == "refresh":
            await self.coordinator.async_request_refresh()
