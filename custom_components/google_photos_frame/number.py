"""Number platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import GooglePhotosFrameConfigEntry


NUMBER_DESCRIPTIONS = [
    NumberEntityDescription(
        key="display_interval",
        translation_key="display_interval",
        icon="mdi:timer-outline",
        native_min_value=5,
        native_max_value=3600,
        native_step=5,
        native_unit_of_measurement="s",
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="refresh_interval",
        translation_key="refresh_interval",
        icon="mdi:refresh",
        native_min_value=1,
        native_max_value=1440,
        native_step=1,
        native_unit_of_measurement="min",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number platform."""
    coordinator = entry.runtime_data
    store = coordinator.store
    async_add_entities(
        [
            GooglePhotosFrameNumber(coordinator, entry, description, store)
            for description in NUMBER_DESCRIPTIONS
        ]
    )


class GooglePhotosFrameNumber(GooglePhotosFrameEntity, NumberEntity, RestoreEntity):
    """Number entity for configurable settings."""

    entity_description: NumberEntityDescription
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: NumberEntityDescription,
        store,
    ) -> None:
        """Initialize number entity."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(last_state.state)
                # Update store with restored value
                if self.entity_description.key == "display_interval":
                    self._store.display_interval = int(self._attr_native_value)
                elif self.entity_description.key == "refresh_interval":
                    self._store.refresh_interval = int(self._attr_native_value)
            except (ValueError, TypeError):
                pass

        # Listen for store changes
        self._store.add_listener(self._on_store_change)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        self._store.remove_listener(self._on_store_change)

    def _on_store_change(self) -> None:
        """Handle store change."""
        if self.entity_description.key == "display_interval":
            self._attr_native_value = float(self._store.display_interval)
        elif self.entity_description.key == "refresh_interval":
            self._attr_native_value = float(self._store.refresh_interval)
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Return current value."""
        if self.entity_description.key == "display_interval":
            return float(self._store.display_interval)
        elif self.entity_description.key == "refresh_interval":
            return float(self._store.refresh_interval)
        return 0.0

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        int_value = int(value)

        if self.entity_description.key == "display_interval":
            self._store.display_interval = int_value
        elif self.entity_description.key == "refresh_interval":
            self._store.refresh_interval = int_value
            # Update coordinator refresh interval
            self.coordinator.update_interval_minutes = int_value

        self._store.notify()
        self.async_write_ha_state()
