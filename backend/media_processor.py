import os
import sys
import uuid
import asyncio
import subprocess
import logging
import re
import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import yt_dlp
from backend.config import FFMPEG_PATH, TEMP_DIR

logger = logging.getLogger("SonicAM.MediaProcessor")

class MediaProcessor:
    @staticmethod
    def generate_temp_path(extension: str = "wav") -> Path:
        """Generate unique temporary file path."""
        filename = f"sonic_{uuid.uuid4().hex[:12]}.{extension.lstrip('.')}"
        return TEMP_DIR / filename

    @classmethod
    def cleanup_file(cls, filepath: Optional[Path]) -> None:
        """Safely remove a temporary file."""
        if filepath and filepath.exists():
            try:
                filepath.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not delete temp file {filepath}: {e}")

    @classmethod
    async def extract_audio_from_file(
        cls,
        input_path: Path,
        start_time: int = 0,
        duration: int = 45
    ) -> Path:
        """
        Extract audio from any video/audio file into normalized 44.1kHz 16-bit WAV.
        Works with MP4, MKV, MOV, WEBM, MP3, M4A, FLAC, OGG, etc.
        """
        output_wav = cls.generate_temp_path("wav")
        ffmpeg_bin = FFMPEG_PATH or "ffmpeg"
        
        # Primary attempt: fast seek with primary audio stream map
        cmd1 = [
            ffmpeg_bin,
            "-y",
            "-ss", str(start_time),
            "-i", str(input_path),
            "-map", "0:a:0?",
            "-t", str(duration),
            "-vn",                       # strip video stream
            "-acodec", "pcm_s16le",       # uncompressed PCM 16-bit
            "-ar", "44100",              # 44.1 kHz
            "-ac", "2",                  # stereo
            str(output_wav)
        ]
        
        logger.info(f"Extracting audio using FFmpeg: {' '.join(cmd1)}")
        process = await asyncio.create_subprocess_exec(
            *cmd1,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        err_msg = stderr.decode(errors="replace")

        # Detect silent videos with no audio stream
        if process.returncode != 0 and any(s in err_msg.lower() for s in ["does not contain any stream", "matches no streams", "no audio stream", "output file #0 does not contain any stream"]):
            cls.cleanup_file(output_wav)
            raise ValueError("This video file does not contain an audio track. Please upload a video with sound.")
        
        # Fallback attempt: output seek without -map if fast seek failed
        if process.returncode != 0 or not output_wav.exists() or output_wav.stat().st_size == 0:
            logger.warning(f"Fast seek extraction failed (code {process.returncode}), attempting output seek fallback...")
            cls.cleanup_file(output_wav)
            cmd2 = [
                ffmpeg_bin,
                "-y",
                "-i", str(input_path),
                "-ss", str(start_time),
                "-t", str(duration),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(output_wav)
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd2,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            err_msg = stderr.decode(errors="replace")
        
        if process.returncode != 0:
            if any(s in err_msg.lower() for s in ["does not contain any stream", "matches no streams", "no audio stream"]):
                cls.cleanup_file(output_wav)
                raise ValueError("This video file does not contain an audio track. Please upload a video with sound.")
            cls.cleanup_file(output_wav)
            raise RuntimeError(f"Audio extraction failed: {err_msg[-300:]}")
            
        if not output_wav.exists() or output_wav.stat().st_size == 0:
            cls.cleanup_file(output_wav)
            raise RuntimeError("FFmpeg generated empty audio output from uploaded media.")
            
        logger.info(f"Audio extracted successfully to {output_wav} ({output_wav.stat().st_size} bytes)")
        return output_wav

    @staticmethod
    def normalize_video_url(raw_url: str) -> Tuple[str, bool, Optional[str]]:
        """
        Normalize video URLs from different platforms (Shorts, youtu.be, mobile shares),
        strip tracking junk, and detect direct media streams.
        Returns (clean_url, is_direct_media, platform_hint).
        """
        # Extract pure URL from surrounding text or markdown
        clean_match = re.search(r'https?://[^\s<>"\')\]]+', raw_url)
        clean_url = clean_match.group(0).rstrip('.,;:') if clean_match else raw_url.strip()

        # Detect platform hint across all major global, video, messaging, forum, decentralized, and regional networks
        platform_hint = None
        lower = clean_url.lower()

        if "youtube.com" in lower or "youtu.be" in lower:
            platform_hint = "youtube"
        elif "instagram.com" in lower or "instagr.am" in lower:
            platform_hint = "instagram"
        elif "tiktok.com" in lower:
            platform_hint = "tiktok"
        elif "twitter.com" in lower or "x.com" in lower or "t.co" in lower:
            platform_hint = "twitter"
        elif "facebook.com" in lower or "fb.watch" in lower or "fb.com" in lower:
            platform_hint = "facebook"
        elif "threads.net" in lower:
            platform_hint = "threads"
        elif "snapchat.com" in lower:
            platform_hint = "snapchat"
        elif "linkedin.com" in lower:
            platform_hint = "linkedin"
        elif "pinterest.com" in lower or "pin.it" in lower:
            platform_hint = "pinterest"
        elif "tumblr.com" in lower:
            platform_hint = "tumblr"
        elif "twitch.tv" in lower:
            platform_hint = "twitch"
        elif "vimeo.com" in lower:
            platform_hint = "vimeo"
        elif "rumble.com" in lower:
            platform_hint = "rumble"
        elif "kick.com" in lower:
            platform_hint = "kick"
        elif "dailymotion.com" in lower or "dai.ly" in lower:
            platform_hint = "dailymotion"
        elif "bilibili.com" in lower or "b23.tv" in lower:
            platform_hint = "bilibili"
        elif "kuaishou.com" in lower or "kwai.com" in lower:
            platform_hint = "kuaishou"
        elif "soundcloud.com" in lower or "snd.sc" in lower:
            platform_hint = "soundcloud"
        elif "reddit.com" in lower or "redd.it" in lower or "v.redd.it" in lower:
            platform_hint = "reddit"
        elif "telegram.org" in lower or "t.me" in lower or "telegram.me" in lower:
            platform_hint = "telegram"
        elif "discord.com" in lower or "discord.gg" in lower or "discordapp.com" in lower or "discordapp.net" in lower:
            platform_hint = "discord"
        elif "whatsapp.com" in lower or "wa.me" in lower:
            platform_hint = "whatsapp"
        elif "bsky.app" in lower or "bsky.social" in lower:
            platform_hint = "bluesky"
        elif "mastodon" in lower or "mstdn" in lower:
            platform_hint = "mastodon"
        elif "lemmy" in lower:
            platform_hint = "lemmy"
        elif "pixelfed" in lower:
            platform_hint = "pixelfed"
        elif "weibo.com" in lower or "weibo.cn" in lower:
            platform_hint = "weibo"
        elif "xiaohongshu.com" in lower or "xhslink.com" in lower:
            platform_hint = "xiaohongshu"
        elif "douyin.com" in lower:
            platform_hint = "douyin"
        elif "vk.com" in lower or "vkontakte.ru" in lower:
            platform_hint = "vk"
        elif "ok.ru" in lower:
            platform_hint = "okru"
        elif "sharechat.com" in lower:
            platform_hint = "sharechat"
        elif "mojapp.in" in lower:
            platform_hint = "moj"
        elif "myjosh.in" in lower:
            platform_hint = "josh"
        elif "github.com" in lower or "raw.githubusercontent.com" in lower:
            platform_hint = "github"

        # Standardize mobile youtube
        if "music.youtube.com" in clean_url.lower():
            clean_url = clean_url.replace("music.youtube.com", "www.youtube.com")
        elif "m.youtube.com" in clean_url.lower():
            clean_url = clean_url.replace("m.youtube.com", "www.youtube.com")

        # YouTube Shorts -> standard watch URL for maximum compatibility
        shorts_match = re.search(r'(?:https?://)?(?:www\.|m\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)', clean_url, re.IGNORECASE)
        if shorts_match:
            video_id = shorts_match.group(1)
            clean_url = f"https://www.youtube.com/watch?v={video_id}"

        # youtu.be/<id> -> youtube.com/watch?v=<id>
        youtu_match = re.search(r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]+)', clean_url, re.IGNORECASE)
        if youtu_match:
            video_id = youtu_match.group(1)
            parsed = urllib.parse.urlparse(clean_url)
            qs = urllib.parse.parse_qs(parsed.query)
            t_param = f"&t={qs['t'][0]}" if 't' in qs else ""
            clean_url = f"https://www.youtube.com/watch?v={video_id}{t_param}"

        # youtube.com/embed/<id> -> youtube.com/watch?v=<id>
        embed_match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]+)', clean_url, re.IGNORECASE)
        if embed_match:
            clean_url = f"https://www.youtube.com/watch?v={embed_match.group(1)}"

        # youtube.com/live/<id> -> youtube.com/watch?v=<id>
        live_match = re.search(r'youtube\.com/live/([a-zA-Z0-9_-]+)', clean_url, re.IGNORECASE)
        if live_match:
            clean_url = f"https://www.youtube.com/watch?v={live_match.group(1)}"

        # Strip tracking query parameters from common social share links
        if any(d in clean_url.lower() for d in ["instagram.com", "threads.net", "facebook.com", "fb.watch"]):
            clean_url = clean_url.split('?')[0]

        # Check for direct media URL (.mp4, .webm, .mov, etc.)
        url_path = clean_url.split('?')[0].lower()
        is_direct = url_path.endswith((
            '.mp4', '.webm', '.mov', '.m4v', '.mkv', '.avi',
            '.mp3', '.wav', '.m4a', '.flac', '.ogg', '.opus', '.aac'
        ))

        return clean_url, is_direct, platform_hint

    @classmethod
    async def extract_audio_from_stream(
        cls,
        stream_url: str,
        start_time: int = 0,
        duration: int = 45,
        headers: Optional[Dict[str, str]] = None
    ) -> Path:
        """
        Directly stream and slice audio from a remote media or stream URL into normalized 44.1kHz WAV.
        Bypasses downloading multi-gigabyte video containers.
        """
        output_wav = cls.generate_temp_path("wav")
        ffmpeg_cmd = [
            FFMPEG_PATH or "ffmpeg",
            "-y"
        ]

        if headers:
            header_str = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
            ffmpeg_cmd.extend(["-headers", header_str])

        # Add robust reconnect options for remote HTTP/HTTPS media streams
        if stream_url.startswith(("http://", "https://")):
            ffmpeg_cmd.extend([
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5"
            ])

        ffmpeg_cmd.extend([
            "-ss", str(start_time),
            "-i", str(stream_url),
            "-t", str(duration),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_wav)
        ])
        logger.info(f"Direct stream demuxing via FFmpeg: {' '.join(ffmpeg_cmd[:8])}...")
        
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            logger.error(f"FFmpeg stream demuxing failed: {err_msg}")
            cls.cleanup_file(output_wav)
            raise RuntimeError(f"FFmpeg stream extraction failed: {err_msg[-200:]}")

        if not output_wav.exists() or output_wav.stat().st_size == 0:
            cls.cleanup_file(output_wav)
            raise RuntimeError("FFmpeg generated empty audio output from stream.")

        return output_wav

    @classmethod
    async def resolve_youtube_fallback(cls, clean_url: str) -> Optional[Dict[str, Any]]:
        """
        Emergency fallback for YouTube videos & Shorts:
        1. Inspects the YouTube video page directly for verified Content ID music metadata
           (e.g. Song: 'Love Story', Artist: 'Indila', Album: 'Mini World').
        2. If found or if falling back to oEmbed title, queries Apple/iTunes catalog with sanitized song keywords.
        3. If song matches, downloads high-speed 20s official AAC preview stream into WAV for acoustic recognition.
        4. If audio preview cannot be fingerprinted, returns rich catalog metadata directly.
        """
        loop = asyncio.get_running_loop()

        def _fetch_page_and_oembed():
            music_info = None
            raw_title = ""
            author = ""
            thumbnail = ""
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            # 1. Fetch YouTube HTML page to extract official Content ID song tags
            try:
                watch_url = clean_url
                if "/shorts/" in clean_url:
                    vid_id = clean_url.split("/shorts/")[-1].split("?")[0]
                    watch_url = f"https://www.youtube.com/watch?v={vid_id}"
                req = urllib.request.Request(watch_url, headers=headers)
                with urllib.request.urlopen(req, timeout=6) as resp:
                    html = resp.read().decode('utf-8', errors='replace')
                    
                    # Pattern 1: VIDEO_ATTRIBUTE_IMAGE_STYLE_SQUARE
                    m_attr = re.search(r'"imageStyle":"VIDEO_ATTRIBUTE_IMAGE_STYLE_SQUARE","title":"(.*?)","subtitle":"(.*?)"(?:,"secondarySubtitle":\{"content":"(.*?)"\})?', html)
                    if m_attr:
                        music_info = {
                            "title": m_attr.group(1).strip(),
                            "artist": m_attr.group(2).strip(),
                            "album": m_attr.group(3).strip() if m_attr.group(3) else None
                        }
                    
                    # Pattern 2: dialogMessages runs
                    if not music_info:
                        m_runs = re.search(r'"dialogMessages":\[\{"runs":(\[.*?\])\}\]', html)
                        if m_runs:
                            try:
                                runs = json.loads(m_runs.group(1))
                                song = None
                                artist = None
                                album = None
                                current_key = None
                                for r in runs:
                                    txt = r.get("text", "").strip().rstrip(":")
                                    if txt in ["Song", "Artist", "Album", "Licensed to YouTube by", "Writers"]:
                                        current_key = txt
                                    elif current_key and txt and txt != ":":
                                        if current_key == "Song" and not song:
                                            song = txt
                                        elif current_key == "Artist" and not artist:
                                            artist = txt
                                        elif current_key == "Album" and not album:
                                            album = txt
                                        current_key = None
                                if song:
                                    music_info = {"title": song, "artist": artist, "album": album}
                            except Exception:
                                pass
            except Exception as e:
                logger.warning(f"YouTube HTML inspection note: {e}")

            # 2. oEmbed for video title and thumbnail fallback
            try:
                oembed_url = f"https://www.youtube.com/oembed?url={urllib.parse.quote(clean_url)}&format=json"
                req_oe = urllib.request.Request(oembed_url, headers=headers)
                with urllib.request.urlopen(req_oe, timeout=5) as resp:
                    oe_data = json.loads(resp.read().decode())
                    raw_title = oe_data.get("title", "")
                    author = oe_data.get("author_name", "")
                    thumbnail = oe_data.get("thumbnail_url", "")
            except Exception as e:
                logger.warning(f"YouTube oEmbed lookup failed: {e}")

            return music_info, raw_title, author, thumbnail

        music_info, raw_title, author, thumbnail = await loop.run_in_executor(None, _fetch_page_and_oembed)
        if not music_info and not raw_title:
            return None

        # Determine search keywords
        clean_title = ""
        if music_info:
            clean_title = music_info["title"]
            if music_info.get("artist"):
                author = music_info["artist"]
        else:
            # Clean video title: remove hashtags, emojis, brackets
            clean_title = re.sub(r'#\w+', '', raw_title)
            clean_title = re.sub(r'[\(\[\{].*?[\)\]\}]', '', clean_title)
            for noise in ["Official Music Video", "Official Video", "Official Audio", "Lyrics", "Lyric Video", "4K Remaster", "Shorts", "Short", "Video"]:
                clean_title = re.sub(re.escape(noise), '', clean_title, flags=re.IGNORECASE)
            clean_title = clean_title.strip()

        # Query iTunes Search API with prioritized candidate queries
        def _search_itunes():
            candidates = []
            if music_info:
                if music_info.get("artist"):
                    candidates.append(f"{music_info['title']} {music_info['artist']}")
                candidates.append(music_info["title"])
            
            if clean_title:
                if author and author.lower() not in clean_title.lower() and not re.search(r'world|channel|records|production|official', author, re.IGNORECASE):
                    candidates.append(f"{clean_title} {author}".strip())
                candidates.append(clean_title.strip())

            for q in candidates:
                if not q or len(q) < 2:
                    continue
                try:
                    itunes_url = f"https://itunes.apple.com/search?term={urllib.parse.quote(q)}&entity=song&limit=1"
                    req = urllib.request.Request(itunes_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = json.loads(resp.read().decode())
                        if data.get("resultCount", 0) > 0:
                            return data
                except Exception as e:
                    logger.warning(f"iTunes query failed for '{q}': {e}")
            return None

        itunes_data = await loop.run_in_executor(None, _search_itunes)

        if itunes_data and itunes_data.get("resultCount", 0) > 0:
            item = itunes_data["results"][0]
            track_name = item.get("trackName", clean_title)
            artist_name = item.get("artistName", author)
            album_name = item.get("collectionName", "") or (music_info.get("album") if music_info else "Single Release")
            genre_name = item.get("primaryGenreName", "Music")
            release_date = (item.get("releaseDate") or "")[:4]
            preview_url = item.get("previewUrl")
            cover_art = (item.get("artworkUrl100") or "").replace("100x100bb", "600x600bb") or thumbnail
            apple_music = item.get("trackViewUrl")
        elif music_info:
            track_name = music_info["title"]
            artist_name = music_info.get("artist") or "Music Artist"
            album_name = music_info.get("album") or "Single Release"
            genre_name = "Music"
            release_date = None
            preview_url = None
            cover_art = thumbnail
            apple_music = None
        else:
            # If iTunes found no song and no music metadata exists in the video,
            # don't falsely return the YouTube video title as a song!
            return None

        search_q = urllib.parse.quote(f"{track_name} {artist_name}")
        if not apple_music:
            apple_music = f"https://music.apple.com/us/search?term={search_q}"

        song_dict = {
            "title": track_name,
            "artist": artist_name,
            "album": album_name,
            "label": "Music Catalog",
            "release_year": release_date,
            "genre": genre_name,
            "cover_art": cover_art,
            "preview_url": preview_url,
            "lyrics": [],
            "has_lyrics": False,
            "offset_seconds": None,
            "links": {
                "shazam": None,
                "spotify": f"https://open.spotify.com/search/{search_q}",
                "apple_music": apple_music,
                "youtube_music": f"https://music.youtube.com/search?q={search_q}"
            }
        }

        # If preview_url is available, download and slice 20s preview so Shazam can do acoustic landmark recognition!
        if preview_url:
            try:
                preview_wav = await cls.extract_audio_from_stream(preview_url, start_time=0, duration=20)
                if preview_wav.exists() and preview_wav.stat().st_size > 0:
                    return {
                        "wav_path": preview_wav,
                        "source_info": {
                            "source_title": raw_title or track_name,
                            "source_uploader": author,
                            "source_thumbnail": cover_art,
                            "webpage_url": clean_url,
                            "fallback_song": song_dict
                        }
                    }
            except Exception as e:
                logger.warning(f"Preview extraction failed: {e}")

        return {
            "direct_result": True,
            "resolved_song": {
                "success": True,
                "matched": True,
                "song": song_dict,
                "source_info": {
                    "source_title": raw_title or track_name,
                    "source_uploader": author,
                    "source_thumbnail": cover_art,
                    "webpage_url": clean_url
                }
            }
        }

    @classmethod
    async def extract_media_from_html_page(
        cls,
        clean_url: str,
        start_time: int = 0,
        duration: int = 20
    ) -> Optional[Tuple[Path, Dict[str, Any]]]:
        """
        Inspect generic web pages (Threads, Bluesky, Mastodon, Reddit, Substack, Medium, Discord, forums)
        for embedded HTML5 <video>, <audio>, or OpenGraph media streams and slice audio directly via FFmpeg.
        """
        loop = asyncio.get_running_loop()
        def _fetch_page_media():
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                req = urllib.request.Request(clean_url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode('utf-8', errors='replace')
                    title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
                    page_title = title_match.group(1).strip() if title_match else ""

                    # OpenGraph Video, Audio & HTML5 media tags
                    og_patterns = [
                        r'<meta[^>]+property=["\']og:video(?::secure_url|:url)?["\'][^>]+content=["\']([^"\']+)["\']',
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:video(?::secure_url|:url)?["\']',
                        r'<meta[^>]+property=["\']og:audio(?::secure_url|:url)?["\'][^>]+content=["\']([^"\']+)["\']',
                        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:audio(?::secure_url|:url)?["\']',
                        r'<meta[^>]+name=["\']twitter:player:stream["\'][^>]+content=["\']([^"\']+)["\']',
                        r'<video[^>]+src=["\']([^"\']+)["\']',
                        r'<source[^>]+src=["\']([^"\']+\.(?:mp4|webm|m4a|mp3|ogg|wav))["\']',
                        r'<audio[^>]+src=["\']([^"\']+)["\']'
                    ]
                    for pat in og_patterns:
                        m = re.search(pat, html, re.IGNORECASE)
                        if m:
                            stream_link = m.group(1)
                            if stream_link.startswith("//"):
                                stream_link = "https:" + stream_link
                            elif not stream_link.startswith("http"):
                                stream_link = urllib.parse.urljoin(clean_url, stream_link)
                            return stream_link, page_title
            except Exception as e:
                logger.debug(f"HTML media extraction note: {e}")
            return None, ""

        stream_url, page_title = await loop.run_in_executor(None, _fetch_page_media)
        if stream_url:
            try:
                wav_path = await cls.extract_audio_from_stream(stream_url, start_time, duration)
                if wav_path and wav_path.exists() and wav_path.stat().st_size > 0:
                    return wav_path, {
                        "source_title": page_title or clean_url.split('/')[-1],
                        "webpage_url": clean_url
                    }
            except Exception as e:
                logger.warning(f"Extracted HTML stream failed demux: {e}")
        return None

    @classmethod
    async def extract_audio_from_url(
        cls,
        url: str,
        start_time: int = 0,
        duration: int = 20
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Extract an audio snippet from any web URL (YouTube, YouTube Shorts, SoundCloud, direct MP4, etc.)
        using a resilient multi-tier pipeline (yt-dlp with quickjs + FFmpeg direct stream fallback).
        Defaults to extracting the first 20 seconds for ultra-fast, high-precision acoustic matching.
        """
        clean_url, is_direct, platform_hint = cls.normalize_video_url(url)
        logger.info(f"Normalized URL: {clean_url} (direct: {is_direct}, platform: {platform_hint})")

        # Tier 0: Direct Media URL (MP4, WEBM, MOV, MP3, etc.)
        if is_direct:
            try:
                wav_path = await cls.extract_audio_from_stream(clean_url, start_time=start_time, duration=duration)
                extracted_info = {
                    "source_title": clean_url.split('/')[-1].split('?')[0],
                    "webpage_url": clean_url
                }
                return wav_path, extracted_info
            except Exception as e:
                logger.warning(f"Direct stream extraction failed, falling back to yt-dlp: {e}")

        output_base = cls.generate_temp_path("snippet")
        outtmpl = str(output_base.parent / f"{output_base.stem}.%(ext)s")

        ydl_opts = {
            'format': 'ba/b/bestaudio/best',
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_PATH,
            'download_ranges': yt_dlp.utils.download_range_func(None, [(start_time, start_time + duration)]),
            'playlist_items': '1',
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'postprocessor_args': [
                '-ar', '44100',
                '-ac', '2'
            ],
            'extractor_args': {
                'youtube': {
                    'player_client': ['visionos', 'android_vr', 'android', 'web'],
                }
            },
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 20,
            'retries': 3,
        }

        # Enable QuickJS for YouTube signature solving if available
        try:
            import quickjs
            ydl_opts['js_runtimes'] = {'quickjs': {}}
        except ImportError:
            pass

        extracted_info = {}
        loop = asyncio.get_running_loop()
        download_err = None

        # Tier 1: Try yt-dlp with range slicing
        def _download_slice():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(clean_url, download=True)

        try:
            info = await loop.run_in_executor(None, _download_slice)
            if info:
                if "entries" in info and info["entries"]:
                    valid_entries = [e for e in info["entries"] if e]
                    if valid_entries:
                        info = valid_entries[0]
                extracted_info = {
                    "source_title": info.get("title"),
                    "source_uploader": info.get("uploader") or info.get("channel"),
                    "source_artist": info.get("artist"),
                    "source_track": info.get("track"),
                    "source_album": info.get("album"),
                    "source_duration": info.get("duration"),
                    "source_thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url", clean_url),
                }
        except Exception as e:
            download_err = e
            logger.warning(f"Tier 1 yt-dlp slice download failed: {e}")

        # Check if Tier 1 produced a valid WAV
        expected_wav = output_base.parent / f"{output_base.stem}.wav"
        if expected_wav.exists() and expected_wav.stat().st_size > 0:
            return expected_wav, extracted_info

        all_matches = [p for p in output_base.parent.glob(f"{output_base.stem}*") if p.is_file() and p.stat().st_size > 0]
        wav_matches = [p for p in all_matches if p.suffix.lower() == ".wav"]
        if wav_matches:
            return wav_matches[0], extracted_info

        if all_matches:
            best_candidate = sorted(all_matches, key=lambda p: p.stat().st_size, reverse=True)[0]
            converted_wav = await cls.extract_audio_from_file(best_candidate, start_time, duration)
            for f in all_matches:
                if f != converted_wav:
                    cls.cleanup_file(f)
            return converted_wav, extracted_info

        # Tier 2: Stream Demux Fallback
        # Resolve format stream URL (without downloading entire video) and slice directly via FFmpeg
        logger.info("Attempting Tier 2 direct stream demux fallback...")
        def _extract_stream_info():
            info_opts = dict(ydl_opts)
            info_opts.pop('download_ranges', None)
            info_opts.pop('postprocessors', None)
            with yt_dlp.YoutubeDL(info_opts) as ydl:
                return ydl.extract_info(clean_url, download=False)

        try:
            info = await loop.run_in_executor(None, _extract_stream_info)
            if info:
                if "entries" in info and info["entries"]:
                    valid_entries = [e for e in info["entries"] if e]
                    if valid_entries:
                        info = valid_entries[0]

                extracted_info = {
                    "source_title": info.get("title"),
                    "source_uploader": info.get("uploader") or info.get("channel"),
                    "source_artist": info.get("artist"),
                    "source_track": info.get("track"),
                    "source_album": info.get("album"),
                    "source_duration": info.get("duration"),
                    "source_thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url", clean_url),
                }

                # Find direct stream URL from audio or progressive format
                stream_url = info.get('url')
                stream_headers = None
                if not stream_url and 'requested_formats' in info:
                    for f in info['requested_formats']:
                        if f.get('acodec') != 'none' and f.get('url'):
                            stream_url = f.get('url')
                            stream_headers = f.get('http_headers')
                            break
                if not stream_url and 'formats' in info:
                    audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none' and f.get('url')]
                    if audio_formats:
                        best_f = audio_formats[-1]
                        stream_url = best_f['url']
                        stream_headers = best_f.get('http_headers')
                    elif info['formats']:
                        best_f = info['formats'][-1]
                        stream_url = best_f.get('url')
                        stream_headers = best_f.get('http_headers')

                if stream_url:
                    stream_wav = await cls.extract_audio_from_stream(
                        stream_url, start_time, duration, headers=stream_headers
                    )
                    if stream_wav.exists() and stream_wav.stat().st_size > 0:
                        logger.info(f"Tier 2 stream demux succeeded: {stream_wav}")
                        return stream_wav, extracted_info
        except Exception as e:
            logger.warning(f"Tier 2 stream demux failed: {e}")

        # Tier 2.4: OpenGraph & HTML5 Video/Audio Stream Extraction Fallback (Threads, Bluesky, Mastodon, Reddit, Substack, Forums)
        try:
            logger.info("Attempting Tier 2.4 OpenGraph & HTML5 media extraction fallback...")
            html_res = await cls.extract_media_from_html_page(clean_url, start_time, duration)
            if html_res:
                logger.info(f"Tier 2.4 HTML media extraction succeeded: {html_res[0]}")
                return html_res
        except Exception as e:
            logger.debug(f"Tier 2.4 HTML detector note: {e}")

        # Tier 2.5: Resilient YouTube Metadata & Preview Fallback
        if platform_hint == "youtube":
            logger.info("Attempting Tier 2.5 YouTube metadata & preview fallback...")
            try:
                fallback_res = await cls.resolve_youtube_fallback(clean_url)
                if fallback_res:
                    if fallback_res.get("wav_path"):
                        return fallback_res["wav_path"], fallback_res.get("source_info", {})
                    elif fallback_res.get("direct_result"):
                        return None, fallback_res
            except Exception as e:
                logger.warning(f"Tier 2.5 YouTube fallback encountered: {e}")

        # Tier 3: Translate any technical exceptions into intelligent, actionable guidance
        err_str = str(download_err).lower() if download_err else ""

        if any(w in err_str for w in ["bot", "sign in", "confirm you", "cookies"]):
            raise RuntimeError(
                "YouTube has restricted direct cloud extraction for this link. "
                "Tip: Upload the video file directly into the 'Upload File' tab, or play the video and use the 'Live Ambient Mic' tab to identify it in seconds!"
            )
        elif any(w in err_str for w in ["login", "private", "require", "unauthorized"]) or platform_hint == "instagram":
            raise RuntimeError(
                "This video is private, restricted, or requires an account login. "
                "Tip: Screen-record or save the clip to your device and drop it into the 'Upload File' tab!"
            )
        elif any(w in err_str for w in ["geo", "country", "not available in your location"]):
            raise RuntimeError(
                "This media stream is geo-restricted in the cloud region. "
                "Tip: Play the song on your device and tap 'Live Ambient Mic' to identify it in seconds!"
            )
        elif platform_hint == "tiktok":
            raise RuntimeError(
                "TikTok has restricted direct link streaming for this clip. "
                "Tip: Screen-record or save the sound and drop it into the 'Upload File' tab!"
            )
        elif platform_hint == "vimeo":
            raise RuntimeError(
                "This Vimeo video is password-protected or restricted. "
                "Please upload the video file directly into the 'Upload File' tab."
            )

        err_detail = str(download_err) if download_err else "Audio extraction could not be completed from this URL."
        clean_detail = re.sub(r'https?://[^\s]+', '', err_detail).strip()
        clean_detail = re.sub(r'ERROR:\s*\[[^\]]+\]\s*', '', clean_detail).strip()
        raise RuntimeError(f"Could not extract audio from link: {clean_detail or err_detail}")

