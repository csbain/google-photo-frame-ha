# Google Photos Frame - Home Assistant Integration

A Home Assistant integration that syncs photos from Google Photos to local storage for photo frame display.

## Features

- OAuth2 authentication via Home Assistant
- Syncs photos from app-created Google Photos albums
- Local storage with hash-based deduplication
- Camera entity for dashboard display
- Sensor entity for album info
- Services for manual sync and photo retrieval

## Requirements

- Home Assistant 2024.1.0 or newer
- Google Cloud Project with Photos Library API enabled
- OAuth2 credentials configured in Home Assistant

## Installation

### HACS

1. Open HACS in Home Assistant
2. Add this repository as a custom repository
3. Search for "Google Photos Frame"
4. Click Install

### Manual

1. Copy `custom_components/google_photos_frame` to your Home Assistant `custom_components` folder
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

## Usage

### Camera Entity

The integration creates a `camera.google_photos_frame` entity that displays a random photo from your album. Add it to your dashboard using a Picture Glance or Picture Entity card.

### Sensor Entity

The `sensor.google_photos_frame_album` entity shows:
- **State**: Album name
- **Attributes**:
  - `media_count`: Number of synced photos
  - `last_sync`: Last sync timestamp
  - `album_id`: Google Photos album ID

### Services

#### `google_photos_frame.sync_now`
Trigger immediate sync of the album.

```yaml
service: google_photos_frame.sync_now
```

#### `google_photos_frame.get_random_photo`
Get a random photo from the synced album.

```yaml
service: google_photos_frame.get_random_photo
```

Returns:
```json
{
  "id": "media_id",
  "filename": "photo.jpg",
  "local_path": "/config/google_photos_frame/photos/abc123_full.jpg",
  "width": 1920,
  "height": 1080,
  "creation_time": "2024-01-15T10:30:00Z"
}
```

## Important Notes

### API Limitations

Due to Google's March 2025 API changes, this integration can only access **albums created by this app**. You cannot access your existing Google Photos albums. The workflow is:

1. Create a new album during setup (or select an existing app-created album)
2. Add photos to that album in Google Photos
3. Photos will sync to Home Assistant automatically

### Sync Interval

Photos are synced at the configured interval (default: 5 minutes). You can adjust this in the integration options.

## License

MIT License
