"""Cache manager for resolution-based image caching."""

from __future__ import annotations

import hashlib
import io
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageFilter, ImageOps

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CACHE_DIR,
    CACHE_DOWNLOAD_MINUTES,
    CACHE_INDEX_FILE,
    CACHE_MAX_ITEMS,
    CACHE_STALE_DAYS,
    FillMode,
    PHOTOS_DIR,
    STORAGE_DIR,
)
from .models import MediaItem

if TYPE_CHECKING:
    from . import GooglePhotosFrameConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class ResolutionCacheEntry:
    """Tracks a resolution-specific cache."""

    resolution: tuple[int, int]  # (width, height)
    fill_mode: str
    last_requested: datetime
    request_count: int = 0
    cached_media_ids: set[str] = field(default_factory=set)


@dataclass
class CacheIndex:
    """Master cache index persisted to disk."""

    resolution_caches: dict[str, ResolutionCacheEntry] = field(default_factory=dict)
    last_cleanup: datetime | None = None

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "resolution_caches": {
                key: {
                    "resolution": entry.resolution,
                    "fill_mode": entry.fill_mode,
                    "last_requested": entry.last_requested.isoformat(),
                    "request_count": entry.request_count,
                    "cached_media_ids": list(entry.cached_media_ids),
                }
                for key, entry in self.resolution_caches.items()
            },
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CacheIndex":
        """Deserialize from dict."""
        index = cls()
        for key, entry_data in data.get("resolution_caches", {}).items():
            index.resolution_caches[key] = ResolutionCacheEntry(
                resolution=tuple(entry_data["resolution"]),
                fill_mode=entry_data["fill_mode"],
                last_requested=datetime.fromisoformat(entry_data["last_requested"]),
                request_count=entry_data.get("request_count", 0),
                cached_media_ids=set(entry_data.get("cached_media_ids", [])),
            )
        if data.get("last_cleanup"):
            index.last_cleanup = datetime.fromisoformat(data["last_cleanup"])
        return index


def _get_cache_key(width: int, height: int, fill_mode: str) -> str:
    """Generate cache key for resolution + fill mode."""
    return f"{width}x{height}:{fill_mode}"


class CacheManager:
    """Manages resolution-based image caching with background processing."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GooglePhotosFrameConfigEntry,
    ) -> None:
        """Initialize cache manager."""
        self.hass = hass
        self.entry = entry

        self._storage_path = Path(hass.config.path(STORAGE_DIR))
        self._photos_path = self._storage_path / PHOTOS_DIR
        self._cache_path = self._storage_path / CACHE_DIR
        self._index_path = self._storage_path / CACHE_INDEX_FILE

        self._index: CacheIndex = CacheIndex()
        self._download_cache: dict[str, tuple[datetime, bytes]] = {}
        self._pending_processing: set[str] = set()

    async def async_initialize(self) -> None:
        """Initialize cache manager, load index."""
        await self.hass.async_add_executor_job(self._ensure_directories)
        await self._load_index()

    def _ensure_directories(self) -> None:
        """Ensure cache directories exist."""
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._photos_path.mkdir(parents=True, exist_ok=True)
        self._cache_path.mkdir(parents=True, exist_ok=True)

    async def _load_index(self) -> None:
        """Load cache index from disk."""
        if self._index_path.exists():
            try:
                content = await self.hass.async_add_executor_job(
                    self._index_path.read_text
                )
                data = json.loads(content)
                self._index = CacheIndex.from_dict(data)
                _LOGGER.debug(
                    "Loaded cache index with %d resolution caches",
                    len(self._index.resolution_caches),
                )
            except (json.JSONDecodeError, OSError, KeyError) as err:
                _LOGGER.warning("Failed to load cache index: %s", err)
                self._index = CacheIndex()

    async def _save_index(self) -> None:
        """Save cache index to disk."""
        try:
            content = json.dumps(self._index.to_dict(), indent=2)
            await self.hass.async_add_executor_job(
                self._index_path.write_text, content
            )
        except OSError as err:
            _LOGGER.warning("Failed to save cache index: %s", err)

    def _get_cache_dir(self, width: int, height: int, fill_mode: str) -> Path:
        """Get cache directory for specific resolution."""
        return self._cache_path / f"{width}x{height}_{fill_mode}"

    def _get_cached_image_path(
        self, media_id: str, width: int, height: int, fill_mode: str
    ) -> Path:
        """Get path for cached image."""
        cache_dir = self._get_cache_dir(width, height, fill_mode)
        media_hash = hashlib.sha256(media_id.encode()).hexdigest()[:16]
        return cache_dir / f"{media_hash}.jpg"

    def record_resolution_request(self, width: int, height: int, fill_mode: str) -> None:
        """Record that a resolution was requested."""
        key = _get_cache_key(width, height, fill_mode)
        now = datetime.now(timezone.utc)

        if key in self._index.resolution_caches:
            entry = self._index.resolution_caches[key]
            entry.last_requested = now
            entry.request_count += 1
        else:
            self._index.resolution_caches[key] = ResolutionCacheEntry(
                resolution=(width, height),
                fill_mode=fill_mode,
                last_requested=now,
                request_count=1,
            )

        # Schedule async save
        self.hass.async_create_task(self._save_index())

    async def get_processed_image(
        self,
        media_item: MediaItem,
        width: int,
        height: int,
        fill_mode: str,
    ) -> bytes | None:
        """Get processed image from cache or process on-demand."""
        # Record this resolution was requested
        self.record_resolution_request(width, height, fill_mode)

        # Check cache
        cache_path = self._get_cached_image_path(media_item.id, width, height, fill_mode)
        if cache_path.exists():
            _LOGGER.debug("Cache hit for %s at %dx%d", media_item.id, width, height)
            key = _get_cache_key(width, height, fill_mode)
            if key in self._index.resolution_caches:
                self._index.resolution_caches[key].cached_media_ids.add(media_item.id)
            try:
                return await self.hass.async_add_executor_job(cache_path.read_bytes)
            except OSError as err:
                _LOGGER.warning("Failed to read cached image: %s", err)

        # Process on-demand
        _LOGGER.debug(
            "Cache miss for %s at %dx%d, processing on-demand",
            media_item.id,
            width,
            height,
        )
        return await self._process_and_cache(media_item, width, height, fill_mode)

    async def _process_and_cache(
        self,
        media_item: MediaItem,
        width: int,
        height: int,
        fill_mode: str,
    ) -> bytes | None:
        """Process image and save to cache."""
        # Get original image data
        image_data = await self._get_image_data(media_item)
        if image_data is None:
            return None

        # Process image
        try:
            processed = await self.hass.async_add_executor_job(
                self._process_image, image_data, width, height, fill_mode
            )
        except Exception as err:
            _LOGGER.warning("Failed to process image %s: %s", media_item.id, err)
            return None

        # Save to cache
        cache_path = self._get_cached_image_path(media_item.id, width, height, fill_mode)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            await self.hass.async_add_executor_job(cache_path.write_bytes, processed)
            _LOGGER.debug("Saved processed image to %s", cache_path)

            # Update index
            key = _get_cache_key(width, height, fill_mode)
            if key in self._index.resolution_caches:
                self._index.resolution_caches[key].cached_media_ids.add(media_item.id)
            await self._save_index()

        except OSError as err:
            _LOGGER.warning("Failed to cache processed image: %s", err)

        return processed

    async def _get_image_data(self, media_item: MediaItem) -> bytes | None:
        """Get image data, using download cache if available."""
        now = datetime.now(timezone.utc)

        # Check download cache
        if media_item.id in self._download_cache:
            cached_time, data = self._download_cache[media_item.id]
            if (now - cached_time) < timedelta(minutes=CACHE_DOWNLOAD_MINUTES):
                return data

        # Load from local path (downloaded by coordinator)
        if media_item.local_path:
            try:
                data = await self.hass.async_add_executor_job(
                    Path(media_item.local_path).read_bytes
                )
                self._download_cache[media_item.id] = (now, data)
                self._prune_download_cache()
                return data
            except OSError as err:
                _LOGGER.warning(
                    "Failed to read local image %s: %s", media_item.local_path, err
                )

        # Download from URL as fallback
        if media_item.url:
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(media_item.url, timeout=30) as resp:
                    resp.raise_for_status()
                    data = await resp.read()
                self._download_cache[media_item.id] = (now, data)
                self._prune_download_cache()
                return data
            except Exception as err:
                _LOGGER.warning("Failed to download image %s: %s", media_item.url, err)

        return None

    def _prune_download_cache(self) -> None:
        """Prune download cache if too large."""
        if len(self._download_cache) > CACHE_MAX_ITEMS:
            # Remove oldest entries
            sorted_items = sorted(
                self._download_cache.items(),
                key=lambda x: x[1][0],
            )
            for key, _ in sorted_items[: len(sorted_items) // 4]:
                del self._download_cache[key]

    def _process_image(
        self, image_data: bytes, width: int, height: int, fill_mode: str
    ) -> bytes:
        """Process image with PIL."""
        img = Image.open(io.BytesIO(image_data))

        # Handle EXIF rotation
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")

        # Apply fill mode
        if fill_mode == FillMode.BLUR:
            img = self._blur_fill(img, width, height)
        elif fill_mode == FillMode.CONTAIN:
            img = self._resize_contain(img, width, height)
        else:  # cover
            img = self._resize_cover(img, width, height)

        # Encode as JPEG
        output = io.BytesIO()
        img.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
        return output.getvalue()

    def _resize_cover(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Resize image to cover canvas (may crop)."""
        src_w, src_h = img.size
        if src_w <= 0 or src_h <= 0:
            return img.resize((target_w, target_h))

        scale = max(target_w / src_w, target_h / src_h)
        new_w = max(1, int(round(src_w * scale)))
        new_h = max(1, int(round(src_h * scale)))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center crop
        left = max(0, int(round((new_w - target_w) / 2)))
        top = max(0, int(round((new_h - target_h) / 2)))

        return resized.crop((left, top, left + target_w, top + target_h))

    def _resize_contain(
        self, img: Image.Image, target_w: int, target_h: int, bg: tuple = (0, 0, 0)
    ) -> Image.Image:
        """Resize image to fit within canvas (letterbox)."""
        src_w, src_h = img.size
        if src_w <= 0 or src_h <= 0:
            return img.resize((target_w, target_h))

        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))

        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center on canvas
        canvas = Image.new("RGB", (target_w, target_h), bg)
        left = (target_w - new_w) // 2
        top = (target_h - new_h) // 2
        canvas.paste(resized.convert("RGB"), (left, top))

        return canvas

    def _blur_fill(self, img: Image.Image, target_w: int, target_h: int) -> Image.Image:
        """Blur-fill: blurred background with centered image on top."""
        # Create blurred background (cover)
        bg = self._resize_cover(img, target_w, target_h)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=24))

        src_w, src_h = img.size
        if src_w <= 0 or src_h <= 0:
            return bg

        # Create centered foreground (contain)
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        fg = img.resize((new_w, new_h), Image.Resampling.LANCZOS).convert("RGB")

        # Paste foreground on background
        left = (target_w - new_w) // 2
        top = (target_h - new_h) // 2
        bg.paste(fg, (left, top))

        return bg

    async def queue_background_processing(self, media_items: list[MediaItem]) -> None:
        """Queue media items for background processing.

        This processes images for all active resolutions in the background.
        """
        # Get active resolutions
        active_resolutions = [
            (entry.resolution, entry.fill_mode)
            for entry in self._index.resolution_caches.values()
            if entry.request_count > 0
        ]

        if not active_resolutions:
            return

        _LOGGER.debug(
            "Queueing background processing for %d items across %d resolutions",
            len(media_items),
            len(active_resolutions),
        )

        # Process in background (low priority)
        for (width, height), fill_mode in active_resolutions:
            key = _get_cache_key(width, height, fill_mode)
            cached_ids = self._index.resolution_caches[key].cached_media_ids

            for item in media_items:
                if item.id not in cached_ids and item.id not in self._pending_processing:
                    self._pending_processing.add(item.id)
                    self.hass.async_create_task(
                        self._process_and_cache(item, width, height, fill_mode)
                    )
                    # Don't flood - process one at a time per resolution
                    break

    async def remove_media(self, media_ids: list[str]) -> None:
        """Remove media from all resolution caches."""
        for entry in self._index.resolution_caches.values():
            for media_id in media_ids:
                if media_id in entry.cached_media_ids:
                    cache_path = self._get_cached_image_path(
                        media_id, *entry.resolution, entry.fill_mode
                    )
                    if cache_path.exists():
                        try:
                            await self.hass.async_add_executor_job(cache_path.unlink)
                        except OSError as err:
                            _LOGGER.warning("Failed to remove cached file: %s", err)
                    entry.cached_media_ids.discard(media_id)

        await self._save_index()
        _LOGGER.info("Removed %d media items from all caches", len(media_ids))

    async def cleanup_stale_resolutions(self, max_age_days: int = CACHE_STALE_DAYS) -> None:
        """Remove resolution caches not requested in max_age_days."""
        import shutil

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=max_age_days)
        removed_count = 0

        keys_to_remove = []
        for key, entry in self._index.resolution_caches.items():
            if entry.last_requested < cutoff:
                cache_dir = self._get_cache_dir(*entry.resolution, entry.fill_mode)
                if cache_dir.exists():
                    try:
                        await self.hass.async_add_executor_job(shutil.rmtree, cache_dir)
                        removed_count += 1
                    except OSError as err:
                        _LOGGER.warning("Failed to remove stale cache dir: %s", err)
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._index.resolution_caches[key]

        self._index.last_cleanup = now
        await self._save_index()

        if removed_count > 0:
            _LOGGER.info(
                "Removed %d stale resolution caches (unused > %d days)",
                removed_count,
                max_age_days,
            )

    async def clear_all(self) -> None:
        """Clear all caches for this entry."""
        import shutil

        # Clear resolution caches
        for entry in self._index.resolution_caches.values():
            cache_dir = self._get_cache_dir(*entry.resolution, entry.fill_mode)
            if cache_dir.exists():
                try:
                    await self.hass.async_add_executor_job(shutil.rmtree, cache_dir)
                except OSError as err:
                    _LOGGER.warning("Failed to remove cache dir: %s", err)

        # Clear index
        self._index = CacheIndex()
        self._download_cache.clear()
        await self._save_index()

        _LOGGER.info("Cleared all caches for entry")
