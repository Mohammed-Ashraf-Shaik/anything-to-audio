import os
import sys
import uuid
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import yt_dlp
from backend.config import FFMPEG_PATH, TEMP_DIR

logger = logging.getLogger("SonicID.MediaProcessor")

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
        
        ffmpeg_cmd = [
            FFMPEG_PATH or "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(input_path),
            "-t", str(duration),
            "-vn",                       # strip video stream
            "-acodec", "pcm_s16le",       # uncompressed PCM 16-bit
            "-ar", "44100",              # 44.1 kHz
            "-ac", "2",                  # stereo
            str(output_wav)
        ]
        
        logger.info(f"Extracting audio using FFmpeg: {' '.join(ffmpeg_cmd)}")
        
        # Run FFmpeg asynchronously
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            logger.error(f"FFmpeg extraction failed (code {process.returncode}): {err_msg}")
            cls.cleanup_file(output_wav)
            raise RuntimeError(f"Audio extraction failed: {err_msg[-300:]}")
            
        if not output_wav.exists() or output_wav.stat().st_size == 0:
            cls.cleanup_file(output_wav)
            raise RuntimeError("FFmpeg generated empty audio output.")
            
        logger.info(f"Audio extracted successfully to {output_wav} ({output_wav.stat().st_size} bytes)")
        return output_wav

    @classmethod
    async def extract_audio_from_url(
        cls,
        url: str,
        duration: int = 45
    ) -> Tuple[Path, Dict[str, Any]]:
        """
        Extract an audio snippet from any web URL (YouTube, TikTok, Reels, SoundCloud, etc.)
        using yt-dlp + FFmpeg. Also extracts source metadata (title, author, tags).
        """
        output_base = cls.generate_temp_path("snippet")
        # Template for yt-dlp
        outtmpl = str(output_base.parent / f"{output_base.stem}.%(ext)s")
        
        ydl_opts = {
            'format': 'ba/b/bestaudio/best',
            'outtmpl': outtmpl,
            'ffmpeg_location': FFMPEG_PATH,
            'download_ranges': yt_dlp.utils.download_range_func(None, [(0, duration)]),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'postprocessor_args': [
                '-ar', '44100',
                '-ac', '2'
            ],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 15,
            'retries': 2,
        }

        extracted_info = {}
        
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info

        loop = asyncio.get_running_loop()
        try:
            info = await loop.run_in_executor(None, _download)
            if info:
                extracted_info = {
                    "source_title": info.get("title"),
                    "source_uploader": info.get("uploader") or info.get("channel"),
                    "source_artist": info.get("artist"),
                    "source_track": info.get("track"),
                    "source_album": info.get("album"),
                    "source_duration": info.get("duration"),
                    "source_thumbnail": info.get("thumbnail"),
                    "webpage_url": info.get("webpage_url", url),
                }
        except Exception as e:
            logger.error(f"yt-dlp download failed: {e}")
            raise RuntimeError(f"Could not extract audio from URL: {str(e)}")

        expected_wav = output_base.parent / f"{output_base.stem}.wav"
        if not expected_wav.exists():
            # Check for other extensions
            matches = list(output_base.parent.glob(f"{output_base.stem}.*"))
            if matches:
                # Convert matched file to wav
                converted_wav = await cls.extract_audio_from_file(matches[0], 0, duration)
                cls.cleanup_file(matches[0])
                return converted_wav, extracted_info
            raise RuntimeError("Audio download completed but output file was not found.")

        return expected_wav, extracted_info
