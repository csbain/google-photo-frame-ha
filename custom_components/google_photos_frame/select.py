"""Select platform for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ASPECT_RATIOS, DEFAULT_ASPECT_RATIO, DEFAULT_FILL_MODE, DEFAULT_ORDER_MODE, DOMAIN, FillMode, OrderMode
from .entity import GooglePhotosFrameEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import GooglePhotosFrameConfigEntry


SELECT_DESCRIPTIONS = [
    SelectEntityDescription(
        key="fill_mode",
        translation_key="fill_mode",
        icon="mdi:aspect-ratio",
        entity_category=EntityCategory.CONFIG,
    ),
    SelectEntityDescription(
        key="order_mode",
        translation_key="order_mode",
        icon="mdi:shuffle-variant",
        entity_category=EntityCategory.CONFIG,
    ),
    SelectEntityDescription(
        key="aspect_ratio",
        translation_key="aspect_ratio",
        icon="mdi:crop",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePhotosFrameConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select platform."""
    coordinator = entry.runtime_data
    store = coordinator.store
    async_add_entities(
        [
            GooglePhotosFrameSelect(coordinator, entry, description, store)
            for description in SELECT_DESCRIPTIONS
        ]
    )


class GooglePhotosFrameSelect(GooglePhotosFrameEntity, SelectEntity, RestoreEntity):
    """Select entity for configurable options."""

    entity_description: SelectEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: GooglePhotosFrameConfigEntry,
        description: SelectEntityDescription,
        store,
    ) -> None:
        """Initialize select entity."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Set options based on key
        if description.key == "fill_mode":
            self._attr_options = [FillMode.BLUR, FillMode.COVER, FillMode.CONTAIN]
        elif description.key == "order_mode":
            self._attr_options = [OrderMode.RANDOM, OrderMode.ALBUM]
        elif description.key == "aspect_ratio":
            self._attr_options = ASPECT_RATIOS

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()

        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self.options:
                self._set_store_value(last_state.state)
                self._attr_current_option = last_state.state

        # Listen for store changes
        self._store.add_listener(self._on_store_change)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        self._store.remove_listener(self._on_store_change)

    def _on_store_change(self) -> None:
        """Handle store change."""
        self._attr_current_option = self._get_store_value()
        self.async_write_ha_state()

    def _get_store_value(self) -> str:
        """Get current value from store."""
        if self.entity_description.key == "fill_mode":
            return self._store.fill_mode
        elif self.entity_description.key == "order_mode":
            return self._store.order_mode
        elif self.entity_description.key == "aspect_ratio":
            return self._store.aspect_ratio
        return self.options[0]

    def _set_store_value(self, value: str) -> None:
        """Set value in store."""
        if self.entity_description.key == "fill_mode":
            self._store.fill_mode = value
        elif self.entity_description.key == "order_mode":
            self._store.order_mode = value
        elif self.entity_description.key == "aspect_ratio":
            self._store.aspect_ratio = value

    @property
    def current_option(self) -> str | None:
        """Return current option."""
        value = self._get_store_value()
        return value if value in self.options else self.options[0]

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        if option not in self.options:
            return

        self._set_store_value(option)
        self._attr_current_option = option
        self._store.notify()
        self.async_write_ha_state()
