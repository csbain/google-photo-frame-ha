"""Runtime settings store for Google Photos Frame."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .const import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_DISPLAY_INTERVAL,
    DEFAULT_FILL_MODE,
    DEFAULT_ORDER_MODE,
    DEFAULT_SYNC_INTERVAL,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


ListenerCallback = Callable[[], None]


@dataclass
class SettingsStore:
    """Runtime settings with persistence and listener support.

    This store manages user-configurable settings that can be changed
    at runtime via UI entities (number, select, etc.) and persist
    across Home Assistant restarts via RestoreEntity pattern.
    """

    # Display settings
    display_interval: int = DEFAULT_DISPLAY_INTERVAL  # seconds
    refresh_interval: int = DEFAULT_SYNC_INTERVAL  # minutes
    order_mode: str = DEFAULT_ORDER_MODE
    fill_mode: str = DEFAULT_FILL_MODE
    aspect_ratio: str = DEFAULT_ASPECT_RATIO

    # Slideshow state
    paused: bool = False

    # Entry reference
    entry: ConfigEntry | None = field(default=None, repr=False)

    # Listeners for state changes
    _listeners: list[ListenerCallback] = field(default_factory=list, repr=False)

    def add_listener(self, callback: ListenerCallback) -> None:
        """Add a listener to be notified of changes."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: ListenerCallback) -> None:
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self) -> None:
        """Notify all listeners of a change."""
        for callback in list(self._listeners):
            callback()

    def to_dict(self) -> dict:
        """Serialize settings to dict for restoration."""
        return {
            "display_interval": self.display_interval,
            "refresh_interval": self.refresh_interval,
            "order_mode": self.order_mode,
            "fill_mode": self.fill_mode,
            "aspect_ratio": self.aspect_ratio,
            "paused": self.paused,
        }

    @classmethod
    def from_dict(cls, data: dict, entry: ConfigEntry | None = None) -> "SettingsStore":
        """Deserialize settings from dict."""
        return cls(
            display_interval=data.get("display_interval", DEFAULT_DISPLAY_INTERVAL),
            refresh_interval=data.get("refresh_interval", DEFAULT_SYNC_INTERVAL),
            order_mode=data.get("order_mode", DEFAULT_ORDER_MODE),
            fill_mode=data.get("fill_mode", DEFAULT_FILL_MODE),
            aspect_ratio=data.get("aspect_ratio", DEFAULT_ASPECT_RATIO),
            paused=data.get("paused", False),
            entry=entry,
        )
