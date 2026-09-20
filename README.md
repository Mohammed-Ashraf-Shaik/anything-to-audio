# 🎵 SonicAM — Anything to Audio & Song Recognition Engine

> **Extract, detect, and identify any song in seconds from links, video files, audio tracks, or live ambient microphone.**

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi)
![Shazam Engine](https://img.shields.io/badge/Shazam-Landmark%20AI-0088ff?style=for-the-badge)
![yt-dlp](https://img.shields.io/badge/yt--dlp-Universal%20Extractor-red?style=for-the-badge)
![FFmpeg](https://img.shields.io/badge/FFmpeg-7.1%20Normalizer-green?style=for-the-badge)

---

## 🌟 Overview

**SonicAM** is an advanced, full-stack music identification platform engineered to solve real-world song recognition problems without relying on paid APIs or restrictive quotas.

Whether you have a **TikTok clip, YouTube Short, Instagram Reel, recorded video file, background audio track, or live music playing around you**, SonicAM extracts the audio, computes neural acoustic landmarks, and matches it against a global database of over 100+ million commercial songs.

---

## 🚀 Key Features

### 1. 🔗 Universal Link Detective (`yt-dlp`)
- Paste any link from **YouTube, YouTube Shorts, TikTok, Instagram Reels, Twitter/X, SoundCloud, Vimeo**, or direct MP4/MP3 URLs.
- Slices only the initial 30–45s audio stream on the fly without downloading giant multi-gigabyte video files.

### 2. 📁 Multi-Container Drag & Drop (`FFmpeg 7.1`)
- Drop any video container (`MP4`, `MKV`, `MOV`, `AVI`, `WEBM`, `FLV`) or audio file (`MP3`, `WAV`, `FLAC`, `M4A`, `OGG`, `AAC`).
- Demuxes the audio track and normalizes it to pristine 44.1kHz 16-bit PCM WAV.

### 3. 🎙️ 15-Second Live Ambient Listening
- Captures ambient music through your browser's microphone with a real-time radial radar countdown.
- **Feedback-Free Audio Isolation**: The microphone input is strictly analyzed for spectrum visualization and never routed into speakers, completely eliminating acoustic feedback loops.
- Supports early stop detection if you want to identify faster.

### 4. 🧠 Shazam Neural Landmark Fingerprinting (`shazamio`)
- Reverse-engineered landmark acoustic algorithm matching commercial audio catalog in 1–2 seconds.
- **Zero API Keys Required**: Operates out-of-the-box.
- **Enriched Metadata Returned**:
  - Song Title & Artist
  - Album Name, Release Year, and Record Label
  - High-Resolution Cover Artwork
  - 30-Second Playable Audio Preview
  - Direct Streaming Links (**Spotify**, **Apple Music**, **YouTube Music**, **Shazam**)
  - Full Synchronized or Plain Lyrics
  - Match Timestamp Offset

### 5. 🎨 Futuristic Glassmorphic UI
- Deep Obsidian (`#07090e`) canvas with electric cyan (`#00f2fe`) and neon violet (`#8a2be2`) glows.
- **Real-Time Canvas Oscilloscope**: Reactive frequency bars dancing to live mic or song previews.
- **Vinyl Record 3D Disc**: Spins out from album artwork during preview playback.
- **Session History Tray**: Saved in `localStorage` for revisiting past discoveries.

---

## 🏗️ Architecture

```
User Input (Link / Video / Audio / Live Mic)
                  │
                  ▼
         FastAPI Async Server
         ┌────────┴────────┐
         │                 │
    (Link/URL)       (File / Mic)
         │                 │
      yt-dlp          Direct Upload
         │                 │
         └────────┬────────┘
                  ▼
        FFmpeg Audio Normalizer
        (44.1kHz PCM 16-bit WAV)
                  │
                  ▼
     Shazam Landmark Fingerprinter
                  │
                  ▼
         Global Music Catalog
                  │
                  ▼
       Structured JSON Response
  (Title, Artist, HD Art, Preview,
   Lyrics, Spotify / Apple Links)
```

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn, Shazamio, yt-dlp, imageio-ffmpeg, pydub
- **Frontend**: Semantic HTML5, Vanilla CSS3 (Custom Glassmorphism Design System), Vanilla ES6 JavaScript, Web Audio API
- **Audio Processing**: FFmpeg 7.1 Static

---

## ⚡ Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/Mohammed-Ashraf-Shaik/anything-to-audio.git
cd anything-to-audio
```

### 2. Create Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Development Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **`http://127.0.0.1:8000`** in your browser to start identifying songs!

---

## 📄 License
MIT License © 2026 Mohammed Ashraf Shaik
