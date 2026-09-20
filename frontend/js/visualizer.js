/**
 * SonicID Audio Visualizer Engine
 * Web Audio API Oscilloscope & Frequency Spectrum Bars
 */

class SonicVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.audioCtx = null;
    this.analyser = null;
    this.sourceNode = null;
    this.dataArray = null;
    this.bufferLength = 0;

    this.mode = 'idle'; // 'idle', 'mic', 'playback'
    this.animationId = null;
    this.phase = 0;

    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
    this.startLoop();
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * (window.devicePixelRatio || 1);
    this.canvas.height = rect.height * (window.devicePixelRatio || 1);
    this.ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    this.displayWidth = rect.width;
    this.displayHeight = rect.height;
  }

  initAudioContext() {
    if (!this.audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioCtx = new AudioCtx();
    }
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
  }

  connectStream(stream) {
    try {
      this.initAudioContext();
      if (this.micSourceNode) {
        try { this.micSourceNode.disconnect(); } catch (e) {}
      }
      
      // Dedicated analyser for microphone that is NEVER connected to audioCtx.destination
      if (!this.micAnalyser) {
        this.micAnalyser = this.audioCtx.createAnalyser();
        this.micAnalyser.fftSize = 128;
        this.micAnalyser.smoothingTimeConstant = 0.85;
      }
      
      this.micSourceNode = this.audioCtx.createMediaStreamSource(stream);
      // Connect ONLY to micAnalyser for visualizer FFT, NEVER to speakers!
      this.micSourceNode.connect(this.micAnalyser);

      this.analyser = this.micAnalyser;
      this.bufferLength = this.micAnalyser.frequencyBinCount;
      this.dataArray = new Uint8Array(this.bufferLength);
      this.setMode('mic');
    } catch (e) {
      console.warn("Could not connect audio stream to visualizer:", e);
      this.setMode('simulated');
    }
  }

  disconnectStream() {
    if (this.micSourceNode) {
      try { this.micSourceNode.disconnect(); } catch (e) {}
      this.micSourceNode = null;
    }
    if (this.mode === 'mic') {
      this.setMode('idle');
    }
  }

  connectAudioElement(audioEl) {
    // Note: Do not attach createMediaElementSource on cross-origin Apple CDN preview streams,
    // as browser security policies silence cross-origin media sources in Web Audio API.
    // The HTML5 <audio> element will output directly to speakers with crystal-clear sound.
    this.setMode('playback-sim');
  }

  setMode(mode) {
    this.mode = mode;
    const statusLabel = document.getElementById('visualizerStatus');
    if (statusLabel) {
      switch (mode) {
        case 'mic':
          statusLabel.textContent = 'LIVE MIC SPECTRUM (ACTIVE)';
          statusLabel.style.color = 'var(--neon-cyan)';
          break;
        case 'playback':
        case 'playback-sim':
          statusLabel.textContent = 'PREVIEW AUDIO SPECTRUM';
          statusLabel.style.color = '#34d399';
          break;
        default:
          statusLabel.textContent = 'IDLE SPECTRUM';
          statusLabel.style.color = 'var(--text-muted)';
      }
    }
  }

  startLoop() {
    const render = () => {
      this.draw();
      this.animationId = requestAnimationFrame(render);
    };
    render();
  }

  draw() {
    const { ctx, displayWidth, displayHeight } = this;
    if (!ctx) return;

    ctx.clearRect(0, 0, displayWidth, displayHeight);

    if (this.mode === 'mic' && this.analyser && this.dataArray) {
      this.analyser.getByteFrequencyData(this.dataArray);
      this.drawFrequencyBars(this.dataArray);
    } else if (this.mode === 'playback' && this.analyser && this.dataArray) {
      this.analyser.getByteFrequencyData(this.dataArray);
      this.drawFrequencyBars(this.dataArray, true);
    } else if (this.mode === 'playback-sim') {
      this.drawSimulatedBeats();
    } else {
      this.drawAmbientWaves();
    }
  }

  drawAmbientWaves() {
    const { ctx, displayWidth, displayHeight } = this;
    this.phase += 0.025;

    const centerY = displayHeight / 2;
    const waveCount = 2;

    for (let w = 0; w < waveCount; w++) {
      ctx.beginPath();
      ctx.lineWidth = w === 0 ? 2 : 1.5;
      
      const grad = ctx.createLinearGradient(0, 0, displayWidth, 0);
      if (w === 0) {
        grad.addColorStop(0, 'rgba(0, 242, 254, 0.1)');
        grad.addColorStop(0.5, 'rgba(79, 172, 254, 0.6)');
        grad.addColorStop(1, 'rgba(138, 43, 226, 0.2)');
      } else {
        grad.addColorStop(0, 'rgba(138, 43, 226, 0.1)');
        grad.addColorStop(0.5, 'rgba(255, 0, 128, 0.4)');
        grad.addColorStop(1, 'rgba(0, 242, 254, 0.2)');
      }
      ctx.strokeStyle = grad;

      for (let x = 0; x < displayWidth; x += 4) {
        const freq = 0.008 + w * 0.004;
        const speed = this.phase * (w === 0 ? 1 : -0.8);
        const y = centerY + Math.sin(x * freq + speed) * 12 * Math.cos(this.phase * 0.5);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  drawFrequencyBars(data, isPlayback = false) {
    const { ctx, displayWidth, displayHeight, bufferLength } = this;
    const barCount = Math.min(bufferLength, 48);
    const barSpacing = 4;
    const totalSpacing = barSpacing * (barCount - 1);
    const barWidth = Math.max(2, (displayWidth - totalSpacing) / barCount);

    for (let i = 0; i < barCount; i++) {
      const val = data[i] || 0;
      const percent = val / 255;
      const barHeight = Math.max(4, percent * (displayHeight - 12));
      const x = i * (barWidth + barSpacing);
      const y = displayHeight - barHeight;

      const grad = ctx.createLinearGradient(0, y, 0, displayHeight);
      if (isPlayback) {
        grad.addColorStop(0, '#34d399');
        grad.addColorStop(0.5, '#00f2fe');
        grad.addColorStop(1, 'rgba(0, 242, 254, 0.2)');
      } else {
        grad.addColorStop(0, '#00f2fe');
        grad.addColorStop(0.5, '#4facfe');
        grad.addColorStop(1, 'rgba(138, 43, 226, 0.2)');
      }

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
      ctx.fill();

      // Top glowing dot
      if (percent > 0.4) {
        ctx.fillStyle = isPlayback ? '#a7f3d0' : '#ffffff';
        ctx.beginPath();
        ctx.arc(x + barWidth / 2, y - 2, 1.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  drawSimulatedBeats() {
    const { ctx, displayWidth, displayHeight } = this;
    this.phase += 0.08;
    const barCount = 42;
    const barSpacing = 4;
    const barWidth = Math.max(2, (displayWidth - barSpacing * (barCount - 1)) / barCount);

    for (let i = 0; i < barCount; i++) {
      const wave = Math.sin(this.phase + i * 0.25) * 0.5 + 0.5;
      const beat = Math.pow(wave, 2);
      const barHeight = Math.max(4, beat * (displayHeight - 15));
      const x = i * (barWidth + barSpacing);
      const y = displayHeight - barHeight;

      const grad = ctx.createLinearGradient(0, y, 0, displayHeight);
      grad.addColorStop(0, '#34d399');
      grad.addColorStop(1, 'rgba(0, 242, 254, 0.2)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
      ctx.fill();
    }
  }
}
