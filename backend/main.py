import os
import sys
import re
import shutil
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.config import FRONTEND_DIR, TEMP_DIR, MAX_FILE_SIZE_BYTES, ALLOWED_EXTENSIONS, FFMPEG_PATH
from backend.media_processor import MediaProcessor
from backend.recognizer import SongRecognizer

logger = logging.getLogger("SonicAM.Server")

app = FastAPI(
    title="SonicAM - Advanced Audio & Music Recognition Engine",
    description="Detect and extract song names, artist details, album art, lyrics, and streaming links from links, videos, audio, and live microphone.",
    version="1.2.3"
)

# Enable CORS for cross-origin integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

recognizer = SongRecognizer()

class UrlRecognizeRequest(BaseModel):
    url: str

@app.get("/api/health")
async def health_check():
    """System health check and diagnostic endpoint."""
    return {
        "status": "healthy",
        "version": "1.2.3",
        "service": "SonicAM Recognition Engine",
        "ffmpeg_configured": FFMPEG_PATH is not None,
        "ffmpeg_path": FFMPEG_PATH,
        "temp_directory": str(TEMP_DIR),
        "allowed_formats": list(ALLOWED_EXTENSIONS)
    }

@app.post("/api/recognize/url")
async def recognize_url(payload: UrlRecognizeRequest):
    """
    Extract audio from any web or social URL (YouTube, TikTok, Instagram, Twitter, SoundCloud, etc.)
    and identify the song. If user enters a song title directly, accurately resolves from global catalog.
    """
    raw_input = payload.url.strip()
    if not raw_input:
        raise HTTPException(status_code=400, detail="Input cannot be empty.")

    # 1. Clean URL or detect if user provided domain without https:// or direct song title
    url = raw_input
    match = re.search(r'https?://[^\s<>"\'\]]+', raw_input)
    if match:
        url = match.group(0).rstrip('.,;:')
    elif re.match(r'^(?:www\.)?(?:youtube\.com|youtu\.be|instagram\.com|tiktok\.com|twitter\.com|x\.com|facebook\.com|fb\.watch|soundcloud\.com|spotify\.com|apple\.com|vimeo\.com|reddit\.com)', raw_input, re.IGNORECASE):
        url = f"https://{raw_input}"
    else:
        # User entered a direct song title/search query like "Snowman Sia" or "Manwa Laage"
        logger.info(f"Direct song title/query received: {raw_input}")
        resolved = await recognizer.resolve_song_from_metadata({"source_title": raw_input})
        if resolved and resolved.get("matched"):
            return resolved

    logger.info(f"Received URL recognition request: {url}")
    wav_path = None
    try:
        wav_path, source_info = await MediaProcessor.extract_audio_from_url(url, duration=45)
        if wav_path is None and source_info and source_info.get("direct_result"):
            return source_info["resolved_song"]

        result = await recognizer.recognize_audio_file(wav_path, source_info=source_info)
        if not result.get("matched"):
            if source_info and "fallback_song" in source_info:
                return {
                    "success": True,
                    "matched": True,
                    "song": source_info["fallback_song"],
                    "source_info": source_info
                }
            # If the video had an intro/dialogue and Shazam missed it, resolve via YouTube metadata
            if source_info and source_info.get("source_title"):
                fallback_res = await MediaProcessor.resolve_youtube_fallback(url)
                if fallback_res:
                    if fallback_res.get("wav_path"):
                        prev_res = await recognizer.recognize_audio_file(fallback_res["wav_path"], source_info=fallback_res.get("source_info"))
                        MediaProcessor.cleanup_file(fallback_res["wav_path"])
                        if prev_res.get("matched"):
                            return prev_res
                    if fallback_res.get("direct_result") and fallback_res.get("resolved_song", {}).get("matched"):
                        return fallback_res["resolved_song"]
                    if fallback_res.get("source_info", {}).get("fallback_song"):
                        return {
                            "success": True,
                            "matched": True,
                            "song": fallback_res["source_info"]["fallback_song"],
                            "source_info": fallback_res["source_info"]
                        }

            # Final attempt: resolve directly from source_info metadata
            resolved = await recognizer.resolve_song_from_metadata(source_info or result.get("source_info"))
            if resolved and resolved.get("matched"):
                return resolved
        return result
    except HTTPException:
        raise
    except RuntimeError as e:
        logger.warning(f"Media extraction note for URL {url}: {e}")
        # If extraction failed, try resolving via title/metadata
        resolved = await recognizer.resolve_song_from_metadata({"source_title": raw_input})
        if resolved and resolved.get("matched"):
            return resolved
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if wav_path:
            MediaProcessor.cleanup_file(wav_path)

@app.post("/api/recognize/file")
async def recognize_file(file: UploadFile = File(...)):
    """
    Extract audio from an uploaded video or audio file (MP4, MKV, MOV, WEBM, MP3, WAV, FLAC, M4A, etc.)
    and identify the song.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    filename_lower = file.filename.lower()
    ext = filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '.{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    logger.info(f"Received file upload: {file.filename} (detected extension: {ext})")
    
    temp_upload = MediaProcessor.generate_temp_path(ext)
    extracted_wav = None
    
    try:
        # Stream file to disk in chunks to handle larger video files safely
        file_size = 0
        with open(temp_upload, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB."
                    )
                buffer.write(chunk)

        logger.info(f"Uploaded file saved to {temp_upload} ({file_size} bytes)")

        # Demux & convert to 44.1kHz WAV segment
        extracted_wav = await MediaProcessor.extract_audio_from_file(temp_upload, start_time=0, duration=45)
        
        # Recognize
        result = await recognizer.recognize_audio_file(
            extracted_wav,
            source_info={
                "filename": file.filename,
                "file_size": file_size,
                "extension": ext
            }
        )
        if not result.get("matched"):
            resolved = await recognizer.resolve_song_from_metadata({
                "filename": file.filename,
                "file_size": file_size,
                "extension": ext
            })
            if resolved and resolved.get("matched"):
                return resolved
        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation issue processing file {file.filename}: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing uploaded file {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        MediaProcessor.cleanup_file(temp_upload)
        if extracted_wav:
            MediaProcessor.cleanup_file(extracted_wav)

@app.post("/api/recognize/mic")
async def recognize_microphone(audio_blob: UploadFile = File(...)):
    """
    Identify song from ambient microphone recording captured in browser.
    """
    logger.info("Received live microphone audio capture.")
    temp_recording = MediaProcessor.generate_temp_path("webm")
    extracted_wav = None
    
    try:
        with open(temp_recording, "wb") as buffer:
            shutil.copyfileobj(audio_blob.file, buffer)

        # Convert webm/ogg/wav mic blob to normalized WAV
        extracted_wav = await MediaProcessor.extract_audio_from_file(temp_recording, start_time=0, duration=30)
        
        result = await recognizer.recognize_audio_file(
            extracted_wav,
            source_info={"source": "Live Ambient Microphone"}
        )
        return result
    except Exception as e:
        logger.error(f"Error processing microphone audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        MediaProcessor.cleanup_file(temp_recording)
        if extracted_wav:
            MediaProcessor.cleanup_file(extracted_wav)

# Mount frontend static assets
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)

