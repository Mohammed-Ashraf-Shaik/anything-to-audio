/**
 * SonicAM Application Logic & API Orchestration
 */

document.addEventListener('DOMContentLoaded', () => {
  // API URL resolver for local web, file:// protocol, and standalone mobile app
  function getApiUrl(endpoint) {
    let base = window.SONICAM_BACKEND_URL || '';
    if (!base && (window.location.protocol === 'file:' || !window.location.origin || window.location.origin === 'null')) {
      base = 'http://localhost:8000';
    }
    if (base) {
      return base.replace(/\/+$/, '') + endpoint;
    }
    return endpoint;
  }

  // Initialize Visualizer
  const visualizer = new SonicVisualizer('visualizerCanvas');

  // DOM Elements
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  // URL Mode Elements
  const urlForm = document.getElementById('urlForm');
  const urlInput = document.getElementById('urlInput');
  const btnPasteUrl = document.getElementById('btnPasteUrl');
  const sampleTags = document.querySelectorAll('.sample-tag');

  // File Upload Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const btnBrowseFile = document.getElementById('btnBrowseFile');
  const dropzonePrompt = document.getElementById('dropzonePrompt');
  const fileSelectedCard = document.getElementById('fileSelectedCard');
  const selectedFileName = document.getElementById('selectedFileName');
  const selectedFileSize = document.getElementById('selectedFileSize');
  const fileTypeIcon = document.getElementById('fileTypeIcon');
  const btnClearFile = document.getElementById('btnClearFile');
  const btnDetectFile = document.getElementById('btnDetectFile');

  // Microphone Elements
  const btnRecordMic = document.getElementById('btnRecordMic');
  const micRadarBox = document.querySelector('.mic-radar-box');
  const micStatusText = document.getElementById('micStatusText');
  const micTimer = document.getElementById('micTimer');

  // Pipeline Steps Elements
  const pipelineSection = document.getElementById('pipelineSection');
  const pipelineHeading = document.getElementById('pipelineHeading');
  const pipelineElapsed = document.getElementById('pipelineElapsed');
  const stepCards = [
    document.getElementById('step1'),
    document.getElementById('step2'),
    document.getElementById('step3'),
    document.getElementById('step4')
  ];

  // Results Showcase Elements
  const resultSection = document.getElementById('resultSection');
  const resultBackdropGlow = document.getElementById('resultBackdropGlow');
  const coverArtContainer = document.querySelector('.cover-art-container');
  const albumCoverImg = document.getElementById('albumCoverImg');
  const genreBadge = document.getElementById('genreBadge');
  const songTitle = document.getElementById('songTitle');
  const songArtist = document.getElementById('songArtist');
  const songAlbum = document.getElementById('songAlbum');
  const songYear = document.getElementById('songYear');
  const pillRelease = document.getElementById('pillRelease');
  const songLabel = document.getElementById('songLabel');
  const pillLabel = document.getElementById('pillLabel');
  const matchOffsetTag = document.getElementById('matchOffsetTag');
  const btnCopySongTitle = document.getElementById('btnCopySongTitle');
  const copyTooltip = document.getElementById('copyTooltip');

  // Preview Player Elements
  const previewPlayerBox = document.getElementById('previewPlayerBox');
  const audioPreviewElement = document.getElementById('audioPreviewElement');
  const btnPlayPreview = document.getElementById('btnPlayPreview');
  const playIcon = btnPlayPreview.querySelector('.play-icon');
  const pauseIcon = btnPlayPreview.querySelector('.pause-icon');
  const playerCurrentTime = document.getElementById('playerCurrentTime');
  const progressBarContainer = document.getElementById('progressBarContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const btnMute = document.getElementById('btnMute');

  // Streaming & Lyrics Elements
  const linkSpotify = document.getElementById('linkSpotify');
  const linkApple = document.getElementById('linkApple');
  const linkYtMusic = document.getElementById('linkYtMusic');
  const linkShazam = document.getElementById('linkShazam');
  const lyricsAccordion = document.getElementById('lyricsAccordion');
  const btnToggleLyrics = document.getElementById('btnToggleLyrics');
  const lyricsContent = document.getElementById('lyricsContent');
  const lyricsText = document.getElementById('lyricsText');
  const btnCopyLyrics = document.getElementById('btnCopyLyrics');
  const btnIdentifyAnother = document.getElementById('btnIdentifyAnother');

  // Not Found Elements
  const notFoundSection = document.getElementById('notFoundSection');
  const notFoundMessage = document.getElementById('notFoundMessage');
  const fallbackBox = document.getElementById('fallbackBox');
  const fallbackTitle = document.getElementById('fallbackTitle');
  const fallbackArtist = document.getElementById('fallbackArtist');
  const btnRetryNotFound = document.getElementById('btnRetryNotFound');

  // History Elements
  const btnOpenHistory = document.getElementById('btnOpenHistory');
  const btnCloseHistory = document.getElementById('btnCloseHistory');
  const historyDrawer = document.getElementById('historyDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const historyList = document.getElementById('historyList');
  const historyEmpty = document.getElementById('historyEmpty');
  const historyCounter = document.getElementById('historyCounter');
  const btnClearHistory = document.getElementById('btnClearHistory');

  // State Variables
  let selectedFile = null;
  let pipelineTimerInterval = null;
  let pipelineStartTime = 0;
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;
  let micTimerInterval = null;
  let micStream = null;
  let historyItems = JSON.parse(localStorage.getItem('sonic_history') || '[]');

  // Initialize
  updateHistoryUI();

  // ==========================================
  // Tab Switching
  // ==========================================
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      const targetId = btn.getAttribute('data-target');
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');

      // Stop mic if recording when switching tabs
      if (isRecording) stopMicRecording();
    });
  });

  // ==========================================
  // URL Input Handlers
  // ==========================================
  if (btnPasteUrl) {
    btnPasteUrl.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          urlInput.focus();
        }
      } catch (err) {
        console.warn('Could not read clipboard:', err);
      }
    });
  }

  sampleTags.forEach(tag => {
    tag.addEventListener('click', () => {
      const sample = tag.getAttribute('data-sample');
      if (sample) {
        urlInput.value = sample;
        urlForm.dispatchEvent(new Event('submit'));
      }
    });
  });

  urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const raw = urlInput.value.trim();
    if (!raw) return;

    // Sanitize and extract pure URL if pasted with prefixes like '1) https://...', quotes, or markdown
    const match = raw.match(/https?:\/\/[^\s<>"')\]]+/i);
    const url = match ? match[0].replace(/[.,;:]+$/, '') : raw;
    urlInput.value = url;

    startPipeline("Connecting to media stream...");
    advancePipelineStep(0);

    try {
      advancePipelineStep(1, "Demuxing and slicing audio stream...");
      
      const response = await fetch(getApiUrl('/api/recognize/url'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      advancePipelineStep(2, "Generating acoustic landmark fingerprints...");
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Server error occurred while analyzing link.");
      }

      advancePipelineStep(3, "Resolving song metadata from global catalog...");
      const data = await response.json();
      
      stopPipeline();
      renderResult(data);
    } catch (err) {
      stopPipeline();
      renderError(err.message);
    }
  });

  // ==========================================
  // File Upload Handlers (Drag & Drop)
  // ==========================================
  btnBrowseFile.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  dropzone.addEventListener('click', () => {
    if (!selectedFile) fileInput.click();
  });

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  ['dragleave', 'dragend'].forEach(type => {
    dropzone.addEventListener(type, () => {
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  function handleFileSelected(file) {
    selectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);
    
    // Determine icon
    const ext = file.name.split('.').pop().toLowerCase();
    const isVideo = ['mp4', 'mkv', 'mov', 'avi', 'webm', 'flv', 'wmv'].includes(ext);
    fileTypeIcon.textContent = isVideo ? '🎬' : '🎵';

    dropzonePrompt.classList.add('hidden');
    fileSelectedCard.classList.remove('hidden');
    btnDetectFile.classList.remove('hidden');
  }

  btnClearFile.addEventListener('click', (e) => {
    e.stopPropagation();
    selectedFile = null;
    fileInput.value = '';
    dropzonePrompt.classList.remove('hidden');
    fileSelectedCard.classList.add('hidden');
    btnDetectFile.classList.add('hidden');
  });

  btnDetectFile.addEventListener('click', async () => {
    if (!selectedFile) return;

    startPipeline("Uploading and parsing media file...");
    advancePipelineStep(0);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      advancePipelineStep(1, "Extracting 44.1kHz audio stream with FFmpeg...");

      const response = await fetch(getApiUrl('/api/recognize/file'), {
        method: 'POST',
        body: formData
      });

      advancePipelineStep(2, "Computing neural acoustic signature...");

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Error extracting audio from file.");
      }

      advancePipelineStep(3, "Querying global music catalog...");
      const data = await response.json();

      stopPipeline();
      renderResult(data);
    } catch (err) {
      stopPipeline();
      renderError(err.message);
    }
  });

  // ==========================================
  // Live Microphone Capture
  // ==========================================
  btnRecordMic.addEventListener('click', () => {
    if (!isRecording) {
      startMicRecording();
    } else {
      stopMicRecording();
    }
  });

  async function startMicRecording() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      visualizer.connectStream(micStream);

      isRecording = true;
      btnRecordMic.classList.add('recording');
      micRadarBox.classList.add('recording');
      micStatusText.textContent = "Listening to ambient audio (15s)... Click mic again to detect early.";
      micStatusText.style.color = "var(--neon-cyan)";
      micTimer.classList.remove('hidden');

      recordedChunks = [];
      const options = MediaRecorder.isTypeSupported('audio/webm') ? { mimeType: 'audio/webm' } : {};
      mediaRecorder = new MediaRecorder(micStream, options);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        if (micStream) {
          micStream.getTracks().forEach(track => track.stop());
          micStream = null;
        }
        visualizer.disconnectStream();

        const audioBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        await uploadMicBlob(audioBlob);
      };

      mediaRecorder.start();

      // 15-second countdown
      let remaining = 15;
      micTimer.textContent = `00:${remaining < 10 ? '0' : ''}${remaining}`;
      clearInterval(micTimerInterval);
      micTimerInterval = setInterval(() => {
        remaining -= 1;
        micTimer.textContent = `00:${remaining < 10 ? '0' : ''}${remaining}`;
        if (remaining <= 0) {
          clearInterval(micTimerInterval);
          if (isRecording) stopMicRecording();
        }
      }, 1000);

    } catch (err) {
      console.error("Microphone access error:", err);
      micStatusText.textContent = "Microphone access denied or unavailable.";
      micStatusText.style.color = "#f87171";
    }
  }

  function stopMicRecording() {
    if (!isRecording) return;
    isRecording = false;
    clearInterval(micTimerInterval);
    btnRecordMic.classList.remove('recording');
    micRadarBox.classList.remove('recording');
    micStatusText.textContent = "Processing ambient recording...";
    micTimer.classList.add('hidden');

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }

  async function uploadMicBlob(blob) {
    startPipeline("Ingesting ambient microphone recording...");
    advancePipelineStep(0);

    const formData = new FormData();
    formData.append('audio_blob', blob, 'ambient_mic.webm');

    try {
      advancePipelineStep(1, "FFmpeg normalizer converting voice/sound clip...");

      const response = await fetch(getApiUrl('/api/recognize/mic'), {
        method: 'POST',
        body: formData
      });

      advancePipelineStep(2, "Fingerprinting acoustic spectrogram...");

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Error recognizing microphone recording.");
      }

      advancePipelineStep(3, "Cross-referencing music catalogs...");
      const data = await response.json();

      stopPipeline();
      renderResult(data);
    } catch (err) {
      stopPipeline();
      renderError(err.message);
    }
  }

  // ==========================================
  // Pipeline Stepper Logic
  // ==========================================
  function startPipeline(initialMsg) {
    pipelineSection.classList.remove('hidden');
    resultSection.classList.add('hidden');
    notFoundSection.classList.add('hidden');
    
    // Smooth scroll to pipeline
    pipelineSection.scrollIntoView({ behavior: 'smooth', block: 'center' });

    pipelineHeading.textContent = initialMsg || "Processing Audio...";
    pipelineStartTime = Date.now();
    pipelineElapsed.textContent = "0.0s";

    stepCards.forEach(c => {
      c.classList.remove('active', 'completed');
    });

    clearInterval(pipelineTimerInterval);
    pipelineTimerInterval = setInterval(() => {
      const sec = ((Date.now() - pipelineStartTime) / 1000).toFixed(1);
      pipelineElapsed.textContent = `${sec}s`;
    }, 100);
  }

  function advancePipelineStep(stepIndex, msg) {
    if (msg) pipelineHeading.textContent = msg;
    stepCards.forEach((c, idx) => {
      if (idx < stepIndex) {
        c.classList.remove('active');
        c.classList.add('completed');
      } else if (idx === stepIndex) {
        c.classList.add('active');
        c.classList.remove('completed');
      } else {
        c.classList.remove('active', 'completed');
      }
    });
  }

  function stopPipeline() {
    clearInterval(pipelineTimerInterval);
    stepCards.forEach(c => c.classList.add('completed'));
    setTimeout(() => {
      pipelineSection.classList.add('hidden');
    }, 400);
  }

  // ==========================================
  // Render Result Showcase
  // ==========================================
  function renderResult(data) {
    if (!data.matched || !data.song) {
      renderNotFound(data);
      return;
    }

    const song = data.song;

    // Album cover
    const fallbackArt = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><rect width='200' height='200' fill='%23111625'/><text x='50%' y='50%' font-size='60' text-anchor='middle' dominant-baseline='middle' fill='%2300f2fe'>🎵</text></svg>";
    albumCoverImg.src = song.cover_art || fallbackArt;
    albumCoverImg.onerror = () => { albumCoverImg.src = fallbackArt; };

    // Dynamic art glow
    if (song.cover_art) {
      resultBackdropGlow.style.background = `radial-gradient(circle, rgba(0, 242, 254, 0.3) 0%, transparent 70%)`;
    }

    // Genre
    genreBadge.textContent = song.genre || "MUSIC";

    // Titles
    songTitle.textContent = song.title;
    songArtist.textContent = song.artist;
    songAlbum.textContent = song.album || "Unknown Album";

    // Release Year
    if (song.release_year) {
      songYear.textContent = song.release_year;
      pillRelease.classList.remove('hidden');
    } else {
      pillRelease.classList.add('hidden');
    }

    // Record Label
    if (song.label && song.label !== "Unknown Label") {
      songLabel.textContent = song.label;
      pillLabel.classList.remove('hidden');
    } else {
      pillLabel.classList.add('hidden');
    }

    // Match Offset
    if (song.offset_seconds !== null && song.offset_seconds !== undefined) {
      matchOffsetTag.textContent = `• MATCHED AT ${song.offset_seconds}s`;
    } else {
      matchOffsetTag.textContent = '';
    }

    // Setup Preview Audio Player
    if (song.preview_url) {
      previewPlayerBox.classList.remove('hidden');
      audioPreviewElement.src = song.preview_url;
      audioPreviewElement.load();
      resetPlayerUI();
      visualizer.connectAudioElement(audioPreviewElement);
    } else {
      previewPlayerBox.classList.add('hidden');
      audioPreviewElement.src = "";
    }

    // Streaming Links
    const links = song.links || {};
    linkSpotify.href = links.spotify || `https://open.spotify.com/search/${encodeURIComponent(song.title + ' ' + song.artist)}`;
    linkApple.href = links.apple_music || `https://music.apple.com/us/search?term=${encodeURIComponent(song.title + ' ' + song.artist)}`;
    linkYtMusic.href = links.youtube_music || `https://music.youtube.com/search?q=${encodeURIComponent(song.title + ' ' + song.artist)}`;
    if (links.shazam) {
      linkShazam.href = links.shazam;
      linkShazam.classList.remove('hidden');
    } else {
      linkShazam.classList.add('hidden');
    }

    // Lyrics Accordion
    if (song.lyrics && song.lyrics.length > 0) {
      lyricsAccordion.classList.remove('hidden');
      lyricsText.textContent = song.lyrics.join('\n');
      lyricsContent.classList.add('hidden');
      lyricsAccordion.classList.remove('open');
    } else {
      lyricsAccordion.classList.add('hidden');
    }

    // Show Result & Scroll
    resultSection.classList.remove('hidden');
    notFoundSection.classList.add('hidden');
    resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Save to History
    saveToHistory(song);
  }

  function renderNotFound(data) {
    notFoundSection.classList.remove('hidden');
    resultSection.classList.add('hidden');

    if (data.message) {
      notFoundMessage.textContent = data.message;
    }

    const fallback = data.fallback_track;
    if (fallback && fallback.title) {
      fallbackBox.classList.remove('hidden');
      fallbackTitle.textContent = fallback.title;
      fallbackArtist.textContent = fallback.artist || "Unknown";
    } else {
      fallbackBox.classList.add('hidden');
    }

    notFoundSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function renderError(errMsg) {
    let displayMsg = errMsg;
    if (errMsg && (errMsg.includes('Failed to fetch') || errMsg.includes('NetworkError') || errMsg.includes('Load failed'))) {
      displayMsg = `Unable to reach SonicAM Cloud recognition engine. Please check your internet connection and try again.`;
    }
    renderNotFound({
      matched: false,
      message: `Analysis failed: ${displayMsg}`
    });
  }

  // ==========================================
  // Audio Preview Player Controls
  // ==========================================
  btnPlayPreview.addEventListener('click', () => {
    if (audioPreviewElement.paused) {
      audioPreviewElement.volume = 1.0;
      audioPreviewElement.muted = false;
      audioPreviewElement.play().catch(err => console.warn('Audio play error:', err));
      playIcon.classList.add('hidden');
      pauseIcon.classList.remove('hidden');
      coverArtContainer.classList.add('playing');
      visualizer.setMode('playback-sim');
    } else {
      audioPreviewElement.pause();
      playIcon.classList.remove('hidden');
      pauseIcon.classList.add('hidden');
      coverArtContainer.classList.remove('playing');
      visualizer.setMode('idle');
    }
  });

  audioPreviewElement.addEventListener('timeupdate', () => {
    const cur = audioPreviewElement.currentTime;
    const dur = audioPreviewElement.duration || 30;
    const pct = (cur / dur) * 100;
    progressBarFill.style.width = `${pct}%`;
    playerCurrentTime.textContent = `${formatTime(cur)} / ${formatTime(dur)}`;
  });

  audioPreviewElement.addEventListener('ended', () => {
    resetPlayerUI();
    coverArtContainer.classList.remove('playing');
    visualizer.setMode('idle');
  });

  progressBarContainer.addEventListener('click', (e) => {
    const rect = progressBarContainer.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = clickX / rect.width;
    if (audioPreviewElement.duration) {
      audioPreviewElement.currentTime = pct * audioPreviewElement.duration;
    }
  });

  btnMute.addEventListener('click', () => {
    audioPreviewElement.muted = !audioPreviewElement.muted;
    btnMute.style.opacity = audioPreviewElement.muted ? '0.4' : '1';
  });

  function resetPlayerUI() {
    playIcon.classList.remove('hidden');
    pauseIcon.classList.add('hidden');
    progressBarFill.style.width = '0%';
    playerCurrentTime.textContent = '0:00 / 0:30';
  }

  // ==========================================
  // Copy & Action Handlers
  // ==========================================
  btnCopySongTitle.addEventListener('click', () => {
    const textToCopy = `${songTitle.textContent} - ${songArtist.textContent}`;
    navigator.clipboard.writeText(textToCopy).then(() => {
      copyTooltip.classList.add('show');
      setTimeout(() => copyTooltip.classList.remove('show'), 1800);
    });
  });

  btnToggleLyrics.addEventListener('click', () => {
    const isClosed = lyricsContent.classList.contains('hidden');
    if (isClosed) {
      lyricsContent.classList.remove('hidden');
      lyricsAccordion.classList.add('open');
    } else {
      lyricsContent.classList.add('hidden');
      lyricsAccordion.classList.remove('open');
    }
  });

  btnCopyLyrics.addEventListener('click', () => {
    if (lyricsText.textContent) {
      navigator.clipboard.writeText(lyricsText.textContent);
      btnCopyLyrics.querySelector('span').textContent = 'Lyrics Copied!';
      setTimeout(() => {
        btnCopyLyrics.querySelector('span').textContent = 'Copy Full Lyrics';
      }, 2000);
    }
  });

  btnIdentifyAnother.addEventListener('click', () => {
    audioPreviewElement.pause();
    resultSection.classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  btnRetryNotFound.addEventListener('click', () => {
    notFoundSection.classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // ==========================================
  // Detection History (Local Storage)
  // ==========================================
  function saveToHistory(song) {
    // Avoid duplicate at top
    historyItems = historyItems.filter(item => !(item.title === song.title && item.artist === song.artist));
    historyItems.unshift({
      title: song.title,
      artist: song.artist,
      album: song.album,
      cover_art: song.cover_art,
      preview_url: song.preview_url,
      genre: song.genre,
      release_year: song.release_year,
      label: song.label,
      links: song.links,
      timestamp: Date.now()
    });

    if (historyItems.length > 20) historyItems.pop();
    localStorage.setItem('sonic_history', JSON.stringify(historyItems));
    updateHistoryUI();
  }

  function updateHistoryUI() {
    historyCounter.textContent = historyItems.length;
    if (historyItems.length === 0) {
      historyEmpty.classList.remove('hidden');
      return;
    }
    historyEmpty.classList.add('hidden');

    // Rebuild list items
    const existingCards = historyList.querySelectorAll('.history-item');
    existingCards.forEach(c => c.remove());

    historyItems.forEach(item => {
      const card = document.createElement('div');
      card.className = 'history-item';
      card.innerHTML = `
        <img src="${item.cover_art || ''}" class="history-thumb" alt="art" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 40 40%22><rect width=%2240%22 height=%2240%22 fill=%22%23222%22/></svg>'">
        <div class="history-details">
          <div class="history-song-title">${escapeHtml(item.title)}</div>
          <div class="history-artist">${escapeHtml(item.artist)}</div>
          <div class="history-time">${timeAgo(item.timestamp)}</div>
        </div>
      `;
      card.addEventListener('click', () => {
        renderResult({ matched: true, song: item });
        closeHistoryDrawer();
      });
      historyList.appendChild(card);
    });
  }

  btnOpenHistory.addEventListener('click', () => {
    historyDrawer.classList.remove('hidden');
    drawerBackdrop.classList.remove('hidden');
  });

  btnCloseHistory.addEventListener('click', closeHistoryDrawer);
  drawerBackdrop.addEventListener('click', closeHistoryDrawer);

  function closeHistoryDrawer() {
    historyDrawer.classList.add('hidden');
    drawerBackdrop.classList.add('hidden');
  }

  btnClearHistory.addEventListener('click', () => {
    historyItems = [];
    localStorage.removeItem('sonic_history');
    updateHistoryUI();
  });

  // ==========================================
  // Utilities
  // ==========================================
  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  function timeAgo(timestamp) {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
});
