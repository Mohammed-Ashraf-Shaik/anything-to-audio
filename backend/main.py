import os
import sys
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
    version="1.0.0"
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
    and identify the song.
    """
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    logger.info(f"Received URL recognition request: {url}")
    wav_path = None
    try:
        wav_path, source_info = await MediaProcessor.extract_audio_from_url(url, duration=45)
        result = await recognizer.recognize_audio_file(wav_path, source_info=source_info)
        return result
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
        return result

    except HTTPException:
        raise
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

