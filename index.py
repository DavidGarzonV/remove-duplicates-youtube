import json
import os
import pickle
import sys
from difflib import SequenceMatcher
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Required scopes for YouTube Data API
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']


def get_youtube_client():
    """
    Gets an authenticated YouTube Data API client
    
    Returns:
        tuple: (youtube client, bool indicating if authenticated)
    """
    creds = None
    token_file = Path('token.pickle')
    config_file = Path('config.json')
    
    # Check if saved token file exists
    if token_file.exists():
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, do login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing credentials...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"⚠️  Error refreshing token: {e}")
                creds = None
        
        if not creds:
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
            
            if not client_id or not client_secret or client_id == 'TU_CLIENT_ID_AQUI':
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
                creds = flow.run_local_server(port=0)
                
                # Save credentials for future use
                with open(token_file, 'wb') as token:
                    pickle.dump(creds, token)
                
                print("\n✓ Authentication successful!")
                
            except Exception as e:
                print(f"\n❌ Error during authentication: {e}")
                return None, False
    
    # Create YouTube service
    try:
        youtube = build('youtube', 'v3', credentials=creds)
        return youtube, True
    except Exception as e:
        print(f"❌ Error creating YouTube client: {e}")
        return None, False


def calculate_similarity(str1, str2):
    """
    Calculates the similarity between two text strings
    
    Args:
        str1 (str): First string
        str2 (str): Second string
        
    Returns:
        float: Similarity value between 0 and 1
    """
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()


def remove_similar_songs(songs, title_threshold=0.8, artist_threshold=0.9):
    """
    Removes similar songs from the list based on title and artist
    Requires that BOTH (title AND artist) exceed their respective thresholds
    
    Args:
        songs (list): List of songs
        title_threshold (float): Similarity threshold for title (0.8 by default)
        artist_threshold (float): Similarity threshold for artist (0.9 by default)
        
    Returns:
        tuple: (filtered list, list of removed songs)
    """
    filtered_songs = []
    removed_songs = []
    
    for i, song in enumerate(songs):
        is_duplicate = False
        
        for filtered_song in filtered_songs:
            # Calculate title and artist similarity separately
            title_similarity = calculate_similarity(song['titulo'], filtered_song['titulo'])
            artist_similarity = calculate_similarity(song['artista'], filtered_song['artista'])
            
            # Only considered duplicate if BOTH exceed their thresholds
            if title_similarity >= title_threshold and artist_similarity >= artist_threshold:
                is_duplicate = True
                removed_songs.append({
                    'cancion': song,
                    'similar_a': filtered_song,
                    'similaridad_titulo': round(title_similarity, 2),
                    'similaridad_artista': round(artist_similarity, 2)
                })
                break
        
        if not is_duplicate:
            filtered_songs.append(song)
    
    return filtered_songs, removed_songs


def get_playlist_items(youtube, playlist_id):
    """
    Gets all videos from a YouTube playlist using pagination
    
    Args:
        youtube: YouTube API client
        playlist_id: Playlist ID
        
    Returns:
        list: List of playlist items
    """
    playlist_items = []
    next_page_token = None
    
    print("\n🔄 Loading playlist...")
    
    while True:
        try:
            request = youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            playlist_items.extend(response.get('items', []))
            print(f"📥 Loaded {len(playlist_items)} videos...")
            
            next_page_token = response.get('nextPageToken')
            
            if not next_page_token:
                break
                
        except Exception as e:
            print(f"⚠️  Error getting playlist items: {e}")
            break
    
    return playlist_items


def remove_videos_from_playlist(youtube, playlist_item_ids):
    """
    Removes videos from a YouTube playlist
    
    Args:
        youtube: Authenticated YouTube API client
        playlist_item_ids (list): List of playlistItem IDs to remove
        
    Returns:
        tuple: (successes, failures)
    """
    success_count = 0
    failed_count = 0
    
    print(f"\n🗑️  Removing {len(playlist_item_ids)} videos from playlist...\n")
    
    for idx, item_id in enumerate(playlist_item_ids, 1):
        try:
            youtube.playlistItems().delete(id=item_id).execute()
            success_count += 1
            print(f"  ✓ [{idx}/{len(playlist_item_ids)}] Video removed")
        except Exception as e:
            failed_count += 1
            print(f"  ✗ [{idx}/{len(playlist_item_ids)}] Error: {e}")
    
    return success_count, failed_count


def get_playlist_songs(playlist_id, youtube):
    """
    Gets all songs from a YouTube playlist
    
    Args:
        playlist_id (str): YouTube playlist ID
        youtube: Authenticated YouTube API client
        
    Returns:
        list: List of songs with their information (includes playlistItemId)
    """
    try:
        # Get basic playlist information
        playlist_request = youtube.playlists().list(
            part='snippet,contentDetails',
            id=playlist_id
        )
        playlist_response = playlist_request.execute()
        
        if not playlist_response.get('items'):
            print("❌ Playlist not found")
            return []
        
        playlist_info = playlist_response['items'][0]
        playlist_title = playlist_info['snippet']['title']
        total_items = playlist_info['contentDetails']['itemCount']
        
        print(f"\n{'='*60}")
        print(f"Playlist: {playlist_title}")
        print(f"Total videos: {total_items}")
        print(f"{'='*60}\n")
        
        # Get all playlist items
        playlist_items = get_playlist_items(youtube, playlist_id)
        
        print(f"\n✓ Loaded {len(playlist_items)} videos from playlist\n")
        
        # Process items and extract information
        songs = []
        for idx, item in enumerate(playlist_items, 1):
            snippet = item['snippet']
            video_id = item['contentDetails']['videoId']
            playlist_item_id = item['id']  # Unique ID of the item in the playlist
            title = snippet['title']
            channel_title = snippet.get('videoOwnerChannelTitle', snippet.get('channelTitle', 'Unknown'))
            
            song_info = {
                'id': video_id,
                'playlistItemId': playlist_item_id,
                'titulo': title,
                'artista': channel_title
            }
            songs.append(song_info)
        
        # Sort alphabetically by title
        songs.sort(key=lambda x: x['titulo'].lower())
        
        # Display sorted songs
        for idx, song in enumerate(songs, 1):
            print(f"{idx}. {song['titulo']} - {song['artista']} (ID: {song['id']})")
        
        # Save to JSON file
        output_data = {
            'playlist_title': playlist_title,
            'total_songs': len(songs),
            'songs': songs
        }
        
        with open('playlist_songs.json', 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Results saved to 'playlist_songs.json'")
        
        return songs
        
    except Exception as e:
        print(f"❌ Error getting playlist: {e}")
        return []


def main():
    """
    Main program function
    """
    print("=== YouTube Playlist Query ===")
    
    # Get authenticated YouTube client
    youtube, is_authenticated = get_youtube_client()
    
    if not is_authenticated or not youtube:
        print("\n❌ Could not authenticate. The program requires authentication.")
        return
    
    print("\n✓ Authentication successful")
    
    # The playlist ID is found in the URL after "list="
    # Example: https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf
    # The ID would be: PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf
    
    playlist_id = input("\nEnter the YouTube playlist ID: ").strip()
    
    if not playlist_id:
        print("❌ Error: You must provide a valid playlist ID")
        return
    
    # Get and display songs
    songs = get_playlist_songs(playlist_id, youtube)
    
    if songs:
        print(f"\n✓ Found {len(songs)} videos in the playlist")
        
        # Ask if user wants to remove duplicates
        eliminar = input("\nDo you want to search and remove duplicate/similar videos? (y/n): ").strip().lower()
        
        if eliminar in ['s', 'y']:
            # Remove similar songs
            print("\n" + "="*60)
            print("Searching for duplicate/similar videos...")
            print("="*60 + "\n")
            
            filtered_songs, removed_songs = remove_similar_songs(songs, title_threshold=0.8, artist_threshold=0.9)
            
            # Show duplicates found
            if removed_songs:
                print(f"\n🗑️  Found {len(removed_songs)} duplicate/similar videos:\n")
                for idx, item in enumerate(removed_songs, 1):
                    print(f"{idx}. ❌ {item['cancion']['titulo']} - {item['cancion']['artista']}")
                    print(f"   Similar to: {item['similar_a']['titulo']} - {item['similar_a']['artista']}")
                    print(f"   Similarity title: {item['similaridad_titulo']*100:.0f}% | artist: {item['similaridad_artista']*100:.0f}%")
                    print()
            
            # Ask if user wants to remove from YouTube
            if removed_songs:
                eliminar_youtube = input(f"\n⚠️  Do you want to remove these {len(removed_songs)} videos from the original YouTube playlist? (y/n): ").strip().lower()
                
                if eliminar_youtube in ['s', 'y']:
                    # Get playlistItem IDs to remove
                    items_to_remove = [item['cancion']['playlistItemId'] for item in removed_songs]
                    
                    # Remove from YouTube
                    success, failed = remove_videos_from_playlist(youtube, items_to_remove)
                    
                    print(f"\n{'='*60}")
                    print(f"✓ Deletion completed:")
                    print(f"  - Videos removed: {success}")
                    print(f"  - Failures: {failed}")
                    print(f"{'='*60}")
                else:
                    print("\n✓ Playlist will not be modified on YouTube")
        else:
            print("\n✓ Duplicate videos will not be removed")
            filtered_songs = songs
            removed_songs = []
        
        # Check if no duplicates found
        if not removed_songs and eliminar in ['s', 'y']:
            print("✓ No duplicate videos found\n")
        
        # Save removed songs
        if removed_songs:
            output_removed = {
                'total_removed': len(removed_songs),
                'removed_songs': removed_songs
            }
            
            with open('playlist_songs_removed.json', 'w', encoding='utf-8') as f:
                json.dump(output_removed, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Duplicate videos saved to 'playlist_songs_removed.json'")
            print(f"📊 Summary: {len(songs)} videos → {len(filtered_songs)} videos (duplicates found: {len(removed_songs)})")
    else:
        print("\n✗ Could not get videos")


if __name__ == "__main__":
    main()
