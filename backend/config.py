import os
import sys
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SonicAM.Config")

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Use writable /tmp directory on Vercel / serverless platforms
import tempfile
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    TEMP_DIR = Path(tempfile.gettempdir()) / "sonic_temp"
else:
    TEMP_DIR = BASE_DIR / "temp_media"

try:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    TEMP_DIR = Path(tempfile.gettempdir())

# Discover & configure FFmpeg executable
FFMPEG_PATH = None

# Check 1: Virtualenv Scripts directory
venv_ffmpeg = Path(sys.executable).parent / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
if venv_ffmpeg.exists():
    FFMPEG_PATH = str(venv_ffmpeg)
else:
    # Check 2: Try imageio-ffmpeg
    try:
        import imageio_ffmpeg
        img_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(img_ffmpeg):
            if os.name != "nt":
                try:
                    os.chmod(img_ffmpeg, 0o755)
                except Exception:
                    pass
            FFMPEG_PATH = img_ffmpeg
    except Exception as e:
        logger.warning(f"imageio_ffmpeg failed: {e}")

    # Check 3: System PATH
    if not FFMPEG_PATH:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            FFMPEG_PATH = system_ffmpeg

# Serverless & Non-standard binary fix:
# Tools like yt-dlp and FFmpegFD require an executable named literally 'ffmpeg' (or 'ffmpeg.exe')
# within PATH or at the binary location. imageio_ffmpeg names binaries e.g. 'ffmpeg-linux-x86_64-v7.0.2'.
if FFMPEG_PATH:
    ffmpeg_file = Path(FFMPEG_PATH)
    expected_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if ffmpeg_file.name.lower() != expected_name:
        try:
            alias_dir = Path(tempfile.gettempdir()) / "sonic_bin"
            alias_dir.mkdir(parents=True, exist_ok=True)
            standard_binary = alias_dir / expected_name
            if not standard_binary.exists() or standard_binary.stat().st_size == 0:
                try:
                    if standard_binary.exists():
                        standard_binary.unlink(missing_ok=True)
                    os.symlink(FFMPEG_PATH, standard_binary)
                except Exception:
                    shutil.copy2(FFMPEG_PATH, standard_binary)
            if os.name != "nt":
                try:
                    os.chmod(standard_binary, 0o755)
                except Exception:
                    pass
            if standard_binary.exists():
                FFMPEG_PATH = str(standard_binary)
                logger.info(f"Created standard ffmpeg executable alias at: {FFMPEG_PATH}")
        except Exception as e:
            logger.warning(f"Could not create ffmpeg alias: {e}")

if FFMPEG_PATH:
    ffmpeg_dir = str(Path(FFMPEG_PATH).parent)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    logger.info(f"FFmpeg located and active: {FFMPEG_PATH}")
    
    # Configure pydub
    try:
        from pydub import AudioSegment
        AudioSegment.converter = FFMPEG_PATH
        AudioSegment.ffmpeg = FFMPEG_PATH
    except ImportError:
        pass
else:
    logger.warning("FFmpeg executable could not be resolved automatically!")

# Constraints
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB max upload
ALLOWED_EXTENSIONS = {
    # Video
    "mp4", "mkv", "mov", "avi", "webm", "flv", "wmv", "3gp", "m4v", "ts", "m2ts", "mts", "3g2", "ogv", "f4v",
    # Audio
    "mp3", "wav", "m4a", "flac", "aac", "ogg", "wma", "opus", "aiff", "aif", "caf", "amr", "alac"
}

