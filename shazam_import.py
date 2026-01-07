import csv
import json
import pickle
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from index import calculate_similarity, get_youtube_client

# Required scopes for YouTube Data API
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def import_songs_from_csv():
    """
    Prompts the user for a CSV file path, reads it, and extracts the Title (C) and Artist (D) columns
    starting from the second row (header+1)

    Returns:
        list: List of tuples (Title, Artist) or an empty list if there is an error
    """
    try:
        # Prompt user for the file path
        csv_path = input("Enter the path to the CSV file: ").strip()
        
        # Validate that the path is not empty
        if not csv_path:
            print("❌ Error: The path cannot be empty")
            return []
        
        songs = []
        seen = set()
        # Read the CSV file
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            # Skip the first row (header)
            next(reader, None)
            # Read from the second row onwards
            for row in reader:
                # Check that the row has enough columns (C=2, D=3)
                if len(row) >= 4:
                    title = row[2]  # Column C (index 2)
                    artist = row[3]  # Column D (index 3)
                    # Ignore header rows and add to the list if both values exist and not already seen
                    if title and artist and not (title.strip().lower() == "title" and artist.strip().lower() == "artist"):
                        key = (title, artist)
                        if key not in seen:
                            songs.append(key)
                            seen.add(key)
        print(f"✅ Successfully imported {len(songs)} unique songs")
        return songs
        
    except FileNotFoundError:
        print(f"❌ Error: File not found at the specified path")
        return []
    except Exception as e:
        print(f"❌ Error reading the file: {e}")
        return []

def get_youtube_client():
    """
    Gets an authenticated YouTube Data API client
    
    Returns:
        tuple: (youtube client, bool indicating if authenticated)
    """
    credentials = None
    token_file = Path('token.pickle')
    config_file = Path('config.json')
    
    # Check if saved token file exists
    if token_file.exists():
        with open(token_file, 'rb') as token:
            credentials = pickle.load(token)
    
    # If no valid credentials, do login
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("🔄 Refreshing credentials...")
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"⚠️  Error refreshing token: {e}")
                credentials = None
        
        if not credentials:
            # Verify that config.json exists with credentials
            if not config_file.exists():
                print("\n" + "="*60)
                print("❌ config.json not found")
                print("="*60)
                print("\nYou need to create a config.json file with your credentials")
                print("from Google Cloud Console (OAuth 2.0 Client ID)")
                print("\nFormat:")
                print('{')
                print('  "client_id": "your_client_id.apps.googleusercontent.com",')
                print('  "client_secret": "your_client_secret"')
                print('}')
                print("\nTo obtain these credentials:")
                print("1. Go to: https://console.cloud.google.com/")
                print("2. Create a project or select an existing one")
                print("3. Enable YouTube Data API v3")
                print("4. Create OAuth 2.0 credentials")
                print("="*60)
                return None, False
            
            # Load credentials from config.json
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            client_id = config_data.get('client_id', '')
            client_secret = config_data.get('client_secret', '')
            
            if not client_id or not client_secret or client_id == 'YOUR_CLIENT_ID_HERE':
                print("\n❌ config.json does not have valid credentials")
                print("Please edit config.json with your real credentials")
                return None, False
            
            # Create credentials file temporarily
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uris": ["http://localhost"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            
            print("\n" + "="*60)
            print("🔐 Starting authentication process with Google")
            print("="*60)
            print("\nYour browser will open to authorize the application")
            print("Select your Google account and authorize access\n")
            
            try:
                flow = InstalledAppFlow.from_client_config(
                    client_config,
                    SCOPES
                )
                credentials = flow.run_local_server(port=0)
                
                # Save credentials for future use
                with open(token_file, 'wb') as token:
                    pickle.dump(credentials, token)
                
                print("\n✓ Authentication successful!")
                
            except Exception as e:
                print(f"\n❌ Error during authentication: {e}")
                return None, False
    
    # Create YouTube service
    try:
        youtube = build('youtube', 'v3', credentials=credentials)
        return youtube, True
    except Exception as e:
        print(f"❌ Error creating YouTube client: {e}")
        return None, False

def get_or_create_shazam_playlist():
    """
    Uses get_youtube_client to search for a playlist named 'shazam songs'.
    If not found, creates it using the YouTube Data API.
    Returns:
        str: The playlist ID, or None if failed.
    """
    youtube, authenticated = get_youtube_client()
    if not authenticated or youtube is None:
        print("❌ Could not authenticate with YouTube API.")
        return None

    playlist_title = "Shazam Songs"
    playlist_id = None

    try:
        # Search for existing playlists with the given title
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50
        )
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"]["title"].strip().lower() == playlist_title:
                playlist_id = item["id"]
                print(f"✅ Playlist '{playlist_title}' found. ID: {playlist_id}")
                return playlist_id

        # If not found, create the playlist
        print(f"ℹ️ Playlist '{playlist_title}' not found. Creating it...")
        create_request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": playlist_title,
                    "description": "Playlist created automatically for Shazam songs import.",
                },
                "status": {
                    "privacyStatus": "private"
                }
            }
        )
        create_response = create_request.execute()
        playlist_id = create_response["id"]
        print(f"✅ Playlist '{playlist_title}' created. ID: {playlist_id}")
        return playlist_id
    except Exception as e:
        print(f"❌ Error finding or creating playlist: {e}")
        return None

def add_songs_to_shazam_playlist():
    """
    Imports songs from CSV, finds/creates the 'Shazam Songs' playlist, searches each song on YouTube,
    and adds the best match to the playlist using calculate_similarity.
    """
    songs = import_songs_from_csv()
    if not songs:
        print("No songs to import.")
        return

    playlist_id = None
    error_str = None
    try:
        playlist_id = get_or_create_shazam_playlist()
    except Exception as e:
        error_str = str(e)

    # If playlist_id is None, check for quota error and always write deduplicated_songs.json
    if not playlist_id:
        # If error_str is not set, try to get it from the last print (get_or_create_shazam_playlist may print error)
        if not error_str:
            error_str = ""
        # Try to get the last error message from the console output (if possible)
        # Check for quota error in error_str or in the playlist_id (if it is an error message)
        if (error_str and ("quota" in error_str.lower() or "quotaExceeded" in error_str or "403" in error_str)) or (playlist_id is None):
            print("Quota error detected while creating/finding playlist. Saving deduplicated CSV songs to CSV file and exiting.")
            with open("deduplicated_songs.csv", "w", encoding="utf-8", newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Title", "Artist"])
                for t, a in songs:
                    writer.writerow([t, a])
            print(f"\n💾 {len(songs)} deduplicated songs saved to 'deduplicated_songs.csv'")
            return
        else:
            print(f"❌ Error finding or creating playlist: {error_str}")
            return

    youtube, authenticated = get_youtube_client()
    if not authenticated or not youtube:
        print("Could not authenticate with YouTube API.")
        return

    unmatched_songs = []
    failed_to_add_songs = []
    # Get all video IDs already in the playlist to avoid duplicates
    def get_playlist_video_ids(youtube, playlist_id):
        video_ids = set()
        next_page_token = None
        while True:
            pl_request = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            pl_response = pl_request.execute()
            for item in pl_response.get("items", []):
                video_ids.add(item["contentDetails"]["videoId"])
            next_page_token = pl_response.get("nextPageToken")
            if not next_page_token:
                break
        return video_ids

    playlist_video_ids = get_playlist_video_ids(youtube, playlist_id)

    for idx, (title, artist) in enumerate(songs, 1):
        print(f"\n🔎 Searching for: {title} - {artist}")
        try:
            # Search for the song on YouTube
            search_query = f"{title} {artist} music"
            search_request = youtube.search().list(
                part="snippet",
                q=search_query,
                type="video",
                videoCategoryId="10",  # 10 is the category for Music
                maxResults=5
            )
            search_response = search_request.execute()

            best_score = 0
            best_video = None
            for item in search_response.get("items", []):
                video_title = item["snippet"]["title"]
                channel_title = item["snippet"].get("channelTitle", "")
                score_title = calculate_similarity(title, video_title)
                score_artist = calculate_similarity(artist, channel_title)
                score = (score_title + score_artist) / 2
                print(f"  Candidate: {video_title} - {channel_title} | Score: {score:.2f}")
                if score > best_score:
                    best_score = score
                    best_video = item

            if best_video and best_score > 0.5:
                video_id = best_video["id"]["videoId"]
                if video_id in playlist_video_ids:
                    print(f"  ⚠️  Video already in playlist, skipping.")
                else:
                    print(f"  🎵 Best match: {best_video['snippet']['title']} - {best_video['snippet'].get('channelTitle', '')} (Score: {best_score:.2f})")
                    # Add to playlist
                    try:
                        add_request = youtube.playlistItems().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "playlistId": playlist_id,
                                    "resourceId": {
                                        "kind": "youtube#video",
                                        "videoId": video_id
                                    }
                                }
                            }
                        )
                        add_request.execute()
                        print(f"  ➕ Added to playlist!")
                        playlist_video_ids.add(video_id)
                    except Exception as e:
                        print(f"  ❌ Error adding to playlist: {e}")
            else:
                print("  ✗ No good match found.")
                unmatched_songs.append({"title": title, "artist": artist})
            time.sleep(1)  # To avoid quota issues
        except Exception as e:
            print(f"  ❌ Error searching for song: {e}")
            error_str = str(e)
            unmatched_songs.append({"title": title, "artist": artist, "error": error_str})
            # If quota or other error, add to failed_to_add_songs
            if "quota" in error_str.lower() or "quotaExceeded" in error_str or "403" in error_str:
                failed_to_add_songs.append({"title": title, "artist": artist, "error": error_str})

    if unmatched_songs:
        with open("unmatched_songs.csv", "w", encoding="utf-8", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Artist", "Error"])
            processed = 0
            for idx, (title, artist) in enumerate(songs, 1):
                if processed >= max_songs:
                    print(f"\nReached max songs for this run: {max_songs}")
                    break
                # Only call the YouTube search API if the song is not already in the playlist
                already_in_playlist = False
                for video_id in playlist_video_ids:
                    # Optionally, you could cache title/artist to video_id mapping for more efficiency
                    # But here we only check by video_id, so we must search
                    pass
                # If the song is already in the playlist by video_id, skip (handled after search)
                print(f"\n🔎 Searching for: {title} - {artist}")
                try:
                    # Search for the song on YouTube only if not already in playlist
                    # (We can't know video_id before search, so we must search, but we skip adding if already present)
                    search_query = f"{title} {artist} music"
                    search_request = youtube.search().list(
                        part="snippet",
                        q=search_query,
                        type="video",
                        videoCategoryId="10",  # 10 is the category for Music
                        maxResults=5
                    )
                    search_response = search_request.execute()

                    best_score = 0
                    best_video = None
                    for item in search_response.get("items", []):
                        video_title = item["snippet"]["title"]
                        channel_title = item["snippet"].get("channelTitle", "")
                        score_title = calculate_similarity(title, video_title)
                        score_artist = calculate_similarity(artist, channel_title)
                        score = (score_title + score_artist) / 2
                        print(f"  Candidate: {video_title} - {channel_title} | Score: {score:.2f}")
                        if score > best_score:
                            best_score = score
                            best_video = item

                    if best_video and best_score > 0.5:
                        video_id = best_video["id"]["videoId"]
                        if video_id in playlist_video_ids:
                            print(f"  ⚠️  Video already in playlist, skipping.")
                        else:
                            print(f"  🎵 Best match: {best_video['snippet']['title']} - {best_video['snippet'].get('channelTitle', '')} (Score: {best_score:.2f})")
                            # Add to playlist
                            try:
                                add_request = youtube.playlistItems().insert(
                                    part="snippet",
                                    body={
                                        "snippet": {
                                            "playlistId": playlist_id,
                                            "resourceId": {
                                                "kind": "youtube#video",
                                                "videoId": video_id
                                            }
                                        }
                                    }
                                )
                                add_request.execute()
                                print(f"  ➕ Added to playlist!")
                                playlist_video_ids.add(video_id)
                            except Exception as e:
                                print(f"  ❌ Error adding to playlist: {e}")
                    else:
                        print("  ✗ No good match found.")
                        unmatched_songs.append({"title": title, "artist": artist})
                    processed += 1
                except Exception as e:
                    print(f"  ❌ Error searching for song: {e}")
                    error_str = str(e)
                    unmatched_songs.append({"title": title, "artist": artist, "error": error_str})
                    # If quota or other error, add to failed_to_add_songs
                    if "quota" in error_str.lower() or "quotaExceeded" in error_str or "403" in error_str:
                        failed_to_add_songs.append({"title": title, "artist": artist, "error": error_str})