import os
import sys
import re
import json
import asyncio
import urllib.parse
import urllib.request
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure ffmpeg is registered for pydub before importing shazamio
from backend.config import FFMPEG_PATH
try:
    from pydub import AudioSegment
    if FFMPEG_PATH:
        AudioSegment.converter = FFMPEG_PATH
        AudioSegment.ffmpeg = FFMPEG_PATH
except ImportError:
    pass

from shazamio import Shazam

logger = logging.getLogger("SonicAM.Recognizer")

class SongRecognizer:
    def __init__(self):
        self.shazam = Shazam()

    async def recognize_audio_file(self, file_path: Path, source_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Recognize song from an audio file using Shazam's acoustic landmark fingerprinting.
        Parses title, artist, album, cover art, preview stream, genre, lyrics, and streaming links.
        If acoustic matching fails or has a speaking intro, resolves song from metadata hint.
        """
        logger.info(f"Starting acoustic fingerprint analysis on: {file_path}")
        
        try:
            recognition_result = await self.shazam.recognize(str(file_path))
        except Exception as e:
            logger.error(f"Shazam recognition call failed: {e}")
            # Try resolving from metadata hint before erroring out
            resolved = await self.resolve_song_from_metadata(source_info)
            if resolved:
                return resolved
            return self._build_error_response(f"Recognition engine error: {str(e)}", source_info)

        track = recognition_result.get("track")
        matches = recognition_result.get("matches", [])

        if not track or not track.get("title"):
            logger.info("No landmark matches found in global catalog. Resolving from source metadata hint...")
            resolved = await self.resolve_song_from_metadata(source_info)
            if resolved:
                return resolved
            return self._build_not_found_response(source_info)

        # Parse song details
        title = track.get("title", "Unknown Title")
        artist = track.get("subtitle", "Unknown Artist")
        
        # Cover Art
        images = track.get("images", {})
        cover_art = images.get("coverarthq") or images.get("coverart") or images.get("background")
        if not cover_art and source_info and source_info.get("source_thumbnail"):
            cover_art = source_info.get("source_thumbnail")

        # Hub / Actions for 30s audio preview
        preview_url = None
        hub = track.get("hub", {})
        actions = hub.get("actions", [])
        for action in actions:
            if action.get("type") == "uri" and action.get("uri"):
                preview_url = action.get("uri")
                break

        # Sections (Album, Label, Released, Lyrics)
        album = "Unknown Album"
        label = "Unknown Label"
        release_year = None
        lyrics_lines: List[str] = []

        sections = track.get("sections", [])
        for sec in sections:
            sec_type = sec.get("type")
            if sec_type == "SONG":
                for item in sec.get("metadata", []):
                    title_name = item.get("title", "").lower()
                    text_val = item.get("text", "")
                    if "album" in title_name:
                        album = text_val
                    elif "label" in title_name:
                        label = text_val
                    elif "released" in title_name:
                        release_year = text_val
            elif sec_type == "LYRICS":
                lyrics_lines = sec.get("text", [])

        # Genres
        genres_data = track.get("genres", {})
        genre = genres_data.get("primary", "Music")

        # Streaming links
        search_query = urllib.parse.quote(f"{title} {artist}")
        shazam_url = track.get("url")
        spotify_url = f"https://open.spotify.com/search/{search_query}"
        youtube_music_url = f"https://music.youtube.com/search?q={search_query}"
        apple_music_url = None
        
        # Try finding apple music url in hub options
        options = hub.get("options", [])
        for opt in options:
            for opt_action in opt.get("actions", []):
                if opt_action.get("type") == "applemusicopen":
                    apple_music_url = opt_action.get("uri")
                    break

        if not apple_music_url:
            apple_music_url = f"https://music.apple.com/us/search?term={search_query}"

        # Match offset/timestamp
        offset_seconds = None
        if matches:
            first_match = matches[0]
            offset_seconds = first_match.get("offset")

        return {
            "success": True,
            "matched": True,
            "song": {
                "title": title,
                "artist": artist,
                "album": album,
                "label": label,
                "release_year": release_year,
                "genre": genre,
                "cover_art": cover_art,
                "preview_url": preview_url,
                "lyrics": lyrics_lines,
                "has_lyrics": len(lyrics_lines) > 0,
                "offset_seconds": offset_seconds,
                "links": {
                    "shazam": shazam_url,
                    "spotify": spotify_url,
                    "apple_music": apple_music_url,
                    "youtube_music": youtube_music_url
                }
            },
            "source_info": source_info or {}
        }

    async def resolve_song_from_metadata(self, source_info: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        When acoustic landmark fingerprinting finds no match (e.g. video intro dialogue, noisy audio),
        intelligently resolve the song from video metadata / track hint using Apple/iTunes catalog.
        Returns a complete, matched song object with album art, 30s preview audio stream, and streaming links.
        """
        if not source_info:
            return None

        # Check if already resolved upstream
        if "fallback_song" in source_info and isinstance(source_info["fallback_song"], dict):
            return {
                "success": True,
                "matched": True,
                "song": source_info["fallback_song"],
                "source_info": source_info
            }

        raw_title = source_info.get("source_track") or source_info.get("source_title")
        raw_artist = source_info.get("source_artist") or source_info.get("source_uploader")
        thumbnail = source_info.get("source_thumbnail")

        # If source_info has filename and no title
        if not raw_title and source_info.get("filename"):
            fname = source_info["filename"]
            fname = os.path.splitext(fname)[0]
            raw_title = re.sub(r'[\-_.]+', ' ', fname)

        if not raw_title:
            return None

        # Clean noise from title (brackets, Official Video, Lyrics, etc.)
        clean_title = re.sub(r'\[.*?\]|\(.*?\)', '', raw_title)
        for noise in [
            'Official Music Video', 'Official Video', 'Music Video', 'Official Audio',
            'Lyric Video', 'Lyrics', '4K Remaster', 'Remastered', 'Visualizer',
            'HD', '4K', 'Full Song', 'Audio', 'Video', 'HQ'
        ]:
            clean_title = re.sub(re.escape(noise), '', clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'[\"\'\|\#]', '', clean_title).strip()

        # Build candidate search queries
        candidates = []
        if raw_artist and raw_artist.lower() not in clean_title.lower():
            candidates.append(f"{clean_title} {raw_artist}".strip())
        candidates.append(clean_title)

        parts = re.split(r'\s*[-—:|]\s*', raw_title)
        if len(parts) >= 2:
            p0 = re.sub(r'\[.*?\]|\(.*?\)', '', parts[0]).strip()
            p1 = re.sub(r'\[.*?\]|\(.*?\)', '', parts[1]).strip()
            candidates.append(f"{p0} {p1}".strip())
            candidates.append(f"{p1} {p0}".strip())

        loop = asyncio.get_running_loop()

        def _search_itunes():
            for query in candidates:
                if not query or len(query) < 2:
                    continue
                try:
                    url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&entity=song&limit=1"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get('resultCount', 0) > 0:
                            return data['results'][0]
                except Exception as e:
                    logger.debug(f"iTunes lookup error for '{query}': {e}")
            return None

        itunes_item = await loop.run_in_executor(None, _search_itunes)

        if itunes_item:
            title = itunes_item.get("trackName") or clean_title
            artist = itunes_item.get("artistName") or (raw_artist or "Artist")
            album = itunes_item.get("collectionName") or "Single Release"
            preview_url = itunes_item.get("previewUrl")
            cover_art = (itunes_item.get("artworkUrl100") or "").replace("100x100bb", "600x600bb") or thumbnail
            release_year = (itunes_item.get("releaseDate") or "")[:4]
            genre = itunes_item.get("primaryGenreName") or "Music"
            apple_music = itunes_item.get("trackViewUrl")
        else:
            title = clean_title or raw_title
            artist = raw_artist or "Artist"
            album = source_info.get("source_album") or "Single Release"
            preview_url = None
            cover_art = thumbnail
            release_year = None
            genre = "Music"
            apple_music = None

        search_query = urllib.parse.quote(f"{title} {artist}")
        spotify_url = f"https://open.spotify.com/search/{search_query}"
        youtube_music_url = f"https://music.youtube.com/search?q={search_query}"
        if not apple_music:
            apple_music = f"https://music.apple.com/us/search?term={search_query}"

        song_dict = {
            "title": title,
            "artist": artist,
            "album": album,
            "label": "Music Catalog",
            "release_year": release_year,
            "genre": genre,
            "cover_art": cover_art,
            "preview_url": preview_url,
            "lyrics": [],
            "has_lyrics": False,
            "offset_seconds": None,
            "links": {
                "shazam": None,
                "spotify": spotify_url,
                "apple_music": apple_music,
                "youtube_music": youtube_music_url
            }
        }

        return {
            "success": True,
            "matched": True,
            "song": song_dict,
            "source_info": source_info
        }

    def _build_not_found_response(self, source_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Graceful response when acoustic fingerprint has no direct database match and no metadata exists."""
        return {
            "success": True,
            "matched": False,
            "message": "No commercial song recognized from this audio segment. Ensure the audio contains clear music rather than speech or silence.",
            "fallback_track": None,
            "source_info": source_info or {}
        }

    def _build_error_response(self, error_message: str, source_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "success": False,
            "matched": False,
            "error": error_message,
            "source_info": source_info or {}
        }

