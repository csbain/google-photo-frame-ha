# Google Photos Frame - Home Assistant Integration

A Home Assistant integration that syncs photos from Google Photos to local storage for photo frame display.

## Features

- OAuth2 authentication via Home Assistant
- Syncs photos from app-created Google Photos albums
- Local storage with hash-based deduplication
- Camera entity for dashboard display
- Configurable display intervals and shuffle modes
- Fill modes (cover, contain, blur) for different aspect ratios
- Thumbnail URLs for external applications
- Automation blueprints included

## Requirements

- Home Assistant 2024.1.0 or newer
- Google Cloud Project with Photos Library API enabled
- OAuth2 credentials configured in Home Assistant

## Installation

### HACS

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots → Custom repositories
4. Add this repository URL: `https://github.com/csbain/google-photo-frame-ha`
5. Select category: Integration
6. Click Add
7. Search for "Google Photos Frame" and click Install

### Manual

1. Copy the `custom_components/google_photos_frame` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Photos Library API
4. Create OAuth2 credentials (Web application)
5. Add authorized redirect URI: `https://my.home-assistant.io/redirect/oauth`
6. Copy Client ID and Client Secret

### Home Assistant Setup

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Google Photos Frame"
4. Enter your Google Cloud OAuth2 credentials when prompted
5. Authorize with Google
6. Select or create an album for your photo frame

## Entities

### Camera
- `camera.google_photos_frame` - Displays photos with automatic rotation

### Sensors
- `sensor.google_photos_frame_album` - Album information and sync status
- `binary_sensor.google_photos_frame_sync_status` - Sync health monitoring

### Controls
- `button.google_photos_frame_next_photo` - Advance to next photo
- `button.google_photos_frame_previous_photo` - Go to previous photo
- `button.google_photos_frame_refresh` - Trigger immediate sync

### Configuration
- `number.google_photos_frame_display_interval` - Photo rotation time (5-3600 seconds)
- `number.google_photos_frame_refresh_interval` - Album sync interval (1-1440 minutes)
- `select.google_photos_frame_fill_mode` - Display mode (cover, contain, blur)
- `select.google_photos_frame_order_mode` - Playback order (random, album)
- `select.google_photos_frame_aspect_ratio` - Target aspect ratio
- `switch.google_photos_frame_paused` - Pause/resume slideshow

## Services

### `google_photos_frame.sync_now`
Trigger immediate sync of the album.

### `google_photos_frame.get_current_photo`
Get the currently displayed photo without advancing.

### `google_photos_frame.get_photos`
Get a list of photos with pagination support.

### `google_photos_frame.next_photo` / `previous_photo`
Navigate photos programmatically.

### `google_photos_frame.set_photo`
Jump to a specific photo by index or ID.

### `google_photos_frame.clear_cache`
Clear cached photos and processed images.

## Important Notes

### API Limitations

Due to Google's March 2025 API changes, this integration can only access **albums created by this app**. You cannot access your existing Google Photos albums. The workflow is:

1. Create a new album during setup (or select an existing app-created album)
2. Add photos to that album in Google Photos
3. Photos will sync to Home Assistant automatically

## License

MIT License
