"""Issue handlers for Google Photos Frame."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

ISSUE_AUTH_FAILED = "auth_failed"
ISSUE_ALBUM_NOT_FOUND = "album_not_found"


def async_create_auth_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create an issue for authentication failure."""
    ir.async_create_issue(
        hass,
        domain="google_photos_frame",
        issue_id=f"{ISSUE_AUTH_FAILED}_{entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_AUTH_FAILED,
        translation_placeholders={"entry_id": entry_id},
    )


def async_delete_auth_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the authentication failure issue."""
    ir.async_delete_issue(
        hass,
        domain="google_photos_frame",
        issue_id=f"{ISSUE_AUTH_FAILED}_{entry_id}",
    )


def async_create_album_issue(hass: HomeAssistant, entry_id: str, album_name: str) -> None:
    """Create an issue for missing album."""
    ir.async_create_issue(
        hass,
        domain="google_photos_frame",
        issue_id=f"{ISSUE_ALBUM_NOT_FOUND}_{entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ALBUM_NOT_FOUND,
        translation_placeholders={"entry_id": entry_id, "album_name": album_name},
    )


def async_delete_album_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the album not found issue."""
    ir.async_delete_issue(
        hass,
        domain="google_photos_frame",
        issue_id=f"{ISSUE_ALBUM_NOT_FOUND}_{entry_id}",
    )
