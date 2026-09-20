import os
import sys
import urllib.parse
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
        """
        logger.info(f"Starting acoustic fingerprint analysis on: {file_path}")
        
        try:
            recognition_result = await self.shazam.recognize(str(file_path))
        except Exception as e:
            logger.error(f"Shazam recognition call failed: {e}")
            return self._build_error_response(f"Recognition engine error: {str(e)}", source_info)

        track = recognition_result.get("track")
        matches = recognition_result.get("matches", [])

        if not track or not track.get("title"):
            logger.info("No landmark matches found in global catalog.")
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

    def _build_not_found_response(self, source_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Graceful response when acoustic fingerprint has no direct database match."""
        fallback_track = None
        if source_info:
            # If yt-dlp pulled video metadata, offer it as hint
            fallback_track = {
                "title": source_info.get("source_track") or source_info.get("source_title"),
                "artist": source_info.get("source_artist") or source_info.get("source_uploader"),
                "album": source_info.get("source_album"),
                "thumbnail": source_info.get("source_thumbnail")
            }

        return {
            "success": True,
            "matched": False,
            "message": "No commercial song recognized from this audio slice. The audio might be speech, ambient noise, or an uncataloged remix.",
            "fallback_track": fallback_track if (fallback_track and fallback_track.get("title")) else None,
            "source_info": source_info or {}
        }

    def _build_error_response(self, error_message: str, source_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "success": False,
            "matched": False,
            "error": error_message,
            "source_info": source_info or {}
        }
