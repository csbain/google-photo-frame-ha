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

### Step 1: Create Google Cloud OAuth2 Credentials

This integration requires your own Google Cloud OAuth2 credentials because it accesses your personal Google Photos. Each user must create their own credentials (this is the standard pattern for Home Assistant Google integrations).

1. **Go to [Google Cloud Console](https://console.cloud.google.com/)**

2. **Create a new project** (or select an existing one)
   - Click the project dropdown at the top → "New Project"
   - Name it something like "Home Assistant Photos"
   - Click "Create"

3. **Enable the Photos Library API**
   - Go to "APIs & Services" → "Library" (in the left sidebar)
   - Search for "Photos Library API"
   - Click on it → Click "Enable"

4. **Configure OAuth Consent Screen** (required before creating credentials)
   - Go to "APIs & Services" → "OAuth consent screen"
   - Select "External" user type → Click "Create"
   - Fill in required fields:
     - **App name**: "Home Assistant Photos Frame" (or any name you like)
     - **User support email**: Your email address
     - **App logo**: (optional, can skip)
     - **App domain**: (optional, can skip all)
     - **Developer contact email**: Your email address
   - Click "Save and Continue"
   - **Scopes**: Click "Save and Continue" (use defaults)
   - **Test users**: Add your own Google email address
   - Click "Save and Continue" → "Back to Dashboard"

5. **Create OAuth2 Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Application type: **Web application**
   - Name: "Home Assistant" (or any name)
   - Under "Authorized redirect URIs", click "Add URI" and enter:
     ```
     https://my.home-assistant.io/redirect/oauth
     ```
   - Click "Create"
   - **Important**: Copy your **Client ID** and **Client Secret** - you'll need these

### Step 2: Add Credentials to Home Assistant

Before adding the integration, you must register your OAuth2 credentials in Home Assistant:

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **Application Credentials** in the left sidebar (or scroll to the bottom)
3. Click **Add Application Credential** (blue button)
4. Fill in the form:
   - **Application**: Select "Google Photos Frame" from the dropdown
   - **Client ID**: Paste your Google Cloud Client ID
   - **Client Secret**: Paste your Google Cloud Client Secret
5. Click **Submit**

### Step 3: Add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** (blue button, bottom right)
3. Search for "Google Photos Frame"
4. Click on it to start setup
5. You'll be redirected to Google to authorize access
6. Sign in with your Google account and grant permissions
7. Select an existing album or create a new one for your photo frame
8. Click **Submit** to complete setup

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
