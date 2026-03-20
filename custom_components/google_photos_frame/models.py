"""Data models for Google Photos Frame."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MediaItem:
    """Represents a synced media item."""

    id: str
    filename: str
    local_path: str
    width: int | None
    height: int | None
    creation_time: str | None
    url: str | None = None  # Download URL for on-demand fetching


@dataclass
class AlbumData:
    """Data stored by the coordinator."""

    album_id: str
    album_name: str
    media_items: list[MediaItem] = field(default_factory=list)
    last_sync: str | None = None
    media_count: int = 0
