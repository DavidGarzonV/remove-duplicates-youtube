# YouTube Playlist Manager - Official API

Updated project to use Google's **official YouTube Data API v3**.

## 📋 Requirements

- Python 3.7 or higher
- A Google account
- OAuth 2.0 credentials from Google Cloud Console

## 🔑 Credentials Setup

### 1. Create project in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable **YouTube Data API v3**:
   - In the side menu: APIs & Services > Library
   - Search for "YouTube Data API v3"
   - Click "Enable"

### 2. Create OAuth 2.0 credentials

1. Go to: APIs & Services > Credentials
2. Click "+ CREATE CREDENTIALS"
3. Select "OAuth 2.0 Client ID"
4. Application type: "Desktop application"
5. Name: "YouTube Playlist Manager" (or your preference)
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

### 3. Configure config.json

Edit the `config.json` file with your credentials:

```json
{
  "client_id": "tu_client_id.apps.googleusercontent.com",
  "client_secret": "tu_client_secret"
}
```

## 🚀 Installation

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

## 💻 Usage

1. **Run the program:**

```bash
python index.py
```

2. **First time:**
   - Your browser will open
   - Select your Google account
   - Authorize the application
   - Credentials will be saved in `token.pickle`

3. **Enter the playlist ID when prompted**

### How to get a playlist ID?

The playlist ID is in the YouTube URL:

**Example:**
```
https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf
```

The ID would be: `PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf`

## 📊 Features

- ✅ **Full access** to all songs (no 100 video limit)
- ✅ Official Google OAuth 2.0 authentication
- ✅ Automatic pagination for large playlists
- ✅ Duplicate detection and removal
- ✅ JSON export
- ✅ Alphabetical sorting
- ✅ Direct deletion from YouTube playlist

## 📝 Generated files

- `playlist_songs.json` - All songs from the playlist
- `playlist_songs_removed.json` - Songs removed as duplicates
- `token.pickle` - Authentication token (refreshes automatically)

## 🔒 Security

- `config.json` and `token.pickle` are in `.gitignore`
- Don't share these files
- You can revoke access from: https://myaccount.google.com/permissions

## ⚠️ API Limits

YouTube Data API v3 has daily quotas:
- **10,000 units per day** (free)
- Reading a playlist consumes approximately 1 unit per 50 videos
- Deleting videos consumes 50 units per video
- For very large playlists, use the API carefully

## 🆚 Advantages vs ytmusicapi

- ✅ Official and stable Google API
- ✅ No artificial pagination limits
- ✅ Better documentation and support
- ✅ Works with any YouTube playlist (not just YouTube Music)
- ✅ Standard OAuth authentication
