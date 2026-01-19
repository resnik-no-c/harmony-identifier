// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const waveformSection = document.getElementById('waveformSection');
const fileName = document.getElementById('fileName');
const clearFile = document.getElementById('clearFile');
const waveformContainer = document.getElementById('waveform');
const playPause = document.getElementById('playPause');
const playIcon = document.getElementById('playIcon');
const pauseIcon = document.getElementById('pauseIcon');
const currentTimeEl = document.getElementById('currentTime');
const durationEl = document.getElementById('duration');
const segmentStartEl = document.getElementById('segmentStart');
const segmentEndEl = document.getElementById('segmentEnd');
const timeSignatureSelect = document.getElementById('timeSignature');
const presetButtons = document.querySelectorAll('.btn-preset');
const granularitySlider = document.getElementById('granularitySlider');
const granularityValue = document.getElementById('granularityValue');
const analyzeBtn = document.getElementById('analyzeBtn');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
const resultsSection = document.getElementById('resultsSection');
const detectedKey = document.getElementById('detectedKey');
const keyConfidence = document.getElementById('keyConfidence');
const keyConfidenceText = document.getElementById('keyConfidenceText');
const chordTimeline = document.getElementById('chordTimeline');

// State
let wavesurfer = null;
let regions = null;
let currentRegion = null;
let currentAudioBuffer = null;
let currentFile = null;
let audioContext = null;
let currentChords = [];
let chordElements = [];
let chordCarousel = null;
let lastActiveChordIndex = -1;

// Carousel drag state
let isDragging = false;
let dragStartX = 0;
let dragStartScrollOffset = 0;
let currentScrollOffset = 0;
let dragDistance = 0;

// Chord templates for detection (chroma vectors for major and minor triads)
const CHORD_TEMPLATES = {
  'C':   [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
  'C#':  [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
  'D':   [0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0],
  'D#':  [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
  'E':   [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
  'F':   [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
  'F#':  [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
  'G':   [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
  'G#':  [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],
  'A':   [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
  'A#':  [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],
  'B':   [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1],
  'Cm':  [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
  'C#m': [0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
  'Dm':  [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0],
  'D#m': [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
  'Em':  [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
  'Fm':  [1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
  'F#m': [0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
  'Gm':  [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0],
  'G#m': [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
  'Am':  [1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
  'A#m': [0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
  'Bm':  [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1],
};

// Krumhansl-Kessler key profiles for key detection
const MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];
const PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// Chord synthesizer using Web Audio API
const ChordSynth = {
  noteFrequencies: {
    'C': 261.63, 'C#': 277.18, 'Db': 277.18,
    'D': 293.66, 'D#': 311.13, 'Eb': 311.13,
    'E': 329.63,
    'F': 349.23, 'F#': 369.99, 'Gb': 369.99,
    'G': 392.00, 'G#': 415.30, 'Ab': 415.30,
    'A': 440.00, 'A#': 466.16, 'Bb': 466.16,
    'B': 493.88
  },

  parseChord(chordName) {
    const match = chordName.match(/^([A-G][#b]?)(.*)/);
    if (!match) return null;
    return { root: match[1], quality: match[2].toLowerCase() };
  },

  getIntervals(quality) {
    if (quality.includes('dim')) return [0, 3, 6];
    if (quality.includes('aug')) return [0, 4, 8];
    if (quality.includes('m7') || quality.includes('min7')) return [0, 3, 7, 10];
    if (quality.includes('maj7')) return [0, 4, 7, 11];
    if (quality.includes('7')) return [0, 4, 7, 10];
    if (quality.includes('m') || quality.includes('min')) return [0, 3, 7];
    return [0, 4, 7];
  },

  getFrequency(root, semitones) {
    const baseFreq = this.noteFrequencies[root];
    if (!baseFreq) return 440;
    return baseFreq * Math.pow(2, semitones / 12);
  },

  play(chordName, duration = 1.0) {
    const parsed = this.parseChord(chordName);
    if (!parsed) return;

    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    const intervals = this.getIntervals(parsed.quality);
    const now = audioContext.currentTime;

    intervals.forEach((semitones) => {
      const freq = this.getFrequency(parsed.root, semitones);
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();

      osc.type = 'triangle';
      osc.frequency.value = freq;

      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.15, now + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.1, now + 0.2);
      gain.gain.setValueAtTime(0.1, now + duration - 0.1);
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

      osc.connect(gain);
      gain.connect(audioContext.destination);

      osc.start(now);
      osc.stop(now + duration);
    });
  },

  getNoteNames(chordName) {
    const parsed = this.parseChord(chordName);
    if (!parsed) return [];

    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    let rootIndex = noteNames.indexOf(parsed.root);

    if (parsed.root.includes('b')) {
      const flatToSharp = { 'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#' };
      rootIndex = noteNames.indexOf(flatToSharp[parsed.root] || parsed.root);
    }

    const intervals = this.getIntervals(parsed.quality);
    return intervals.map(interval => {
      const noteIndex = (rootIndex + interval) % 12;
      return noteNames[noteIndex];
    });
  }
};

// Mandolin chord fingerings
const MandolinChords = {
  'C': [0, 2, 3, 0], 'C#': [1, 3, 4, 1], 'Db': [1, 3, 4, 1],
  'D': [2, 0, 0, 2], 'D#': [3, 1, 1, 3], 'Eb': [3, 1, 1, 3],
  'E': [4, 2, 2, 0], 'F': [5, 3, 3, 1],
  'F#': [6, 4, 4, 2], 'Gb': [6, 4, 4, 2],
  'G': [0, 0, 2, 3], 'G#': [1, 1, 3, 4], 'Ab': [1, 1, 3, 4],
  'A': [2, 2, 0, 0], 'A#': [3, 3, 1, 1], 'Bb': [3, 3, 1, 1],
  'B': [4, 4, 2, 2],
  'Cm': [0, 1, 3, 0], 'C#m': [1, 2, 4, 1], 'Dbm': [1, 2, 4, 1],
  'Dm': [2, 0, 0, 1], 'D#m': [3, 1, 1, 2], 'Ebm': [3, 1, 1, 2],
  'Em': [0, 2, 2, 0], 'Fm': [1, 3, 3, 1],
  'F#m': [2, 4, 4, 2], 'Gbm': [2, 4, 4, 2],
  'Gm': [0, 0, 1, 3], 'G#m': [1, 1, 2, 4], 'Abm': [1, 1, 2, 4],
  'Am': [2, 2, 0, 0], 'A#m': [3, 3, 1, 1], 'Bbm': [3, 3, 1, 1],
  'Bm': [4, 4, 2, 2],
};

function getMandolinFingering(chordName) {
  if (MandolinChords[chordName]) return MandolinChords[chordName];
  const parsed = ChordSynth.parseChord(chordName);
  if (!parsed) return null;
  const simpleChord = parsed.root + (parsed.quality.includes('m') && !parsed.quality.includes('maj') ? 'm' : '');
  if (MandolinChords[simpleChord]) return MandolinChords[simpleChord];
  if (MandolinChords[parsed.root]) return MandolinChords[parsed.root];
  return null;
}

function renderMandolinTab(fingering) {
  if (!fingering) {
    return '<div class="mando-tab mando-tab-unknown">?</div>';
  }
  const strings = ['E', 'A', 'D', 'G'];
  const frets = [...fingering].reverse();
  let html = '<div class="mando-tab"><div class="mando-strings">';
  for (let i = 0; i < 4; i++) {
    const fret = frets[i];
    html += `<div class="mando-string">
      <span class="mando-string-name">${strings[i]}</span>
      <span class="mando-fret">${fret === 'x' ? 'x' : fret}</span>
    </div>`;
  }
  html += '</div></div>';
  return html;
}

function getRomanNumeral(chordName, keyName) {
  if (!chordName || !keyName) return null;

  const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const romanNumerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];

  const keyMatch = keyName.match(/^([A-G][#b]?)\s*(major|minor)?/i);
  if (!keyMatch) return null;

  let keyRoot = keyMatch[1];
  const keyMode = (keyMatch[2] || 'major').toLowerCase();

  const chordParsed = ChordSynth.parseChord(chordName);
  if (!chordParsed) return null;

  let chordRoot = chordParsed.root;
  const chordQuality = chordParsed.quality;

  const flatToSharp = { 'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#' };
  if (flatToSharp[keyRoot]) keyRoot = flatToSharp[keyRoot];
  if (flatToSharp[chordRoot]) chordRoot = flatToSharp[chordRoot];

  const keyIndex = noteNames.indexOf(keyRoot);
  const chordIndex = noteNames.indexOf(chordRoot);
  if (keyIndex === -1 || chordIndex === -1) return null;

  const interval = (chordIndex - keyIndex + 12) % 12;

  const majorIntervals = { 0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6 };
  const minorIntervals = { 0: 0, 2: 1, 3: 2, 5: 3, 7: 4, 8: 5, 10: 6 };

  const scaleIntervals = keyMode === 'minor' ? minorIntervals : majorIntervals;
  let degree = scaleIntervals[interval];

  let prefix = '';
  let suffix = '';

  if (degree === undefined) {
    const intervals = keyMode === 'minor' ? [0, 2, 3, 5, 7, 8, 10] : [0, 2, 4, 5, 7, 9, 11];
    for (let i = 0; i < intervals.length; i++) {
      if (interval === intervals[i] - 1) {
        degree = i;
        prefix = '♭';
        break;
      } else if (interval === intervals[i] + 1 && i < intervals.length - 1) {
        degree = i;
        prefix = '♯';
        break;
      }
    }
    if (degree === undefined) {
      degree = Math.round(interval / 2);
    }
  }

  let numeral = romanNumerals[degree] || '?';

  const isMinorChord = chordQuality.includes('m') && !chordQuality.includes('maj');
  const isDimChord = chordQuality.includes('dim');
  const isAugChord = chordQuality.includes('aug');

  if (isMinorChord || isDimChord) {
    numeral = numeral.toLowerCase();
  }

  if (isDimChord) suffix = '°';
  else if (isAugChord) suffix = '+';
  else if (chordQuality.includes('7')) {
    if (chordQuality.includes('maj7')) suffix = 'maj7';
    else suffix = '7';
  }

  return prefix + numeral + suffix;
}

// Audio Analysis Functions

// Detect tempo using autocorrelation on onset strength
function detectTempo(audioBuffer, sampleRate) {
  const channelData = audioBuffer.getChannelData(0);

  // Compute onset strength (simple energy derivative)
  const hopSize = 512;
  const frameSize = 2048;
  const energies = [];

  for (let i = 0; i < channelData.length - frameSize; i += hopSize) {
    let energy = 0;
    for (let j = 0; j < frameSize; j++) {
      energy += channelData[i + j] * channelData[i + j];
    }
    energies.push(Math.sqrt(energy / frameSize));
  }

  // Compute onset strength (positive derivatives)
  const onsetStrength = [];
  for (let i = 1; i < energies.length; i++) {
    onsetStrength.push(Math.max(0, energies[i] - energies[i - 1]));
  }

  // Autocorrelation to find tempo
  const minBPM = 60;
  const maxBPM = 200;
  const framesPerSecond = sampleRate / hopSize;
  const minLag = Math.floor(framesPerSecond * 60 / maxBPM);
  const maxLag = Math.floor(framesPerSecond * 60 / minBPM);

  let bestLag = minLag;
  let bestCorr = -Infinity;

  for (let lag = minLag; lag <= maxLag && lag < onsetStrength.length / 2; lag++) {
    let corr = 0;
    for (let i = 0; i < onsetStrength.length - lag; i++) {
      corr += onsetStrength[i] * onsetStrength[i + lag];
    }
    if (corr > bestCorr) {
      bestCorr = corr;
      bestLag = lag;
    }
  }

  const tempo = (framesPerSecond * 60) / bestLag;
  return Math.round(tempo);
}

// Extract chroma features using Meyda
function extractChroma(audioBuffer, startTime, endTime, hopSize = 2048) {
  const sampleRate = audioBuffer.sampleRate;
  const startSample = Math.floor(startTime * sampleRate);
  const endSample = Math.floor(endTime * sampleRate);
  const channelData = audioBuffer.getChannelData(0).slice(startSample, endSample);

  // Initialize Meyda analyzer
  const bufferSize = 2048;
  const chromaFrames = [];

  // Process in chunks
  for (let i = 0; i < channelData.length - bufferSize; i += hopSize) {
    const frame = channelData.slice(i, i + bufferSize);

    // Meyda expects a specific buffer size, ensure we have enough data
    if (frame.length < bufferSize) break;

    try {
      const features = Meyda.extract(['chroma'], frame);
      if (features && features.chroma) {
        chromaFrames.push(features.chroma);
      }
    } catch (e) {
      // Skip frames that fail
    }
  }

  return chromaFrames;
}

// Detect key using Krumhansl-Schmuckler algorithm
function detectKey(chromaFrames) {
  if (chromaFrames.length === 0) {
    return { key: 'C major', confidence: 0 };
  }

  // Average chroma across all frames
  const avgChroma = new Array(12).fill(0);
  for (const frame of chromaFrames) {
    for (let i = 0; i < 12; i++) {
      avgChroma[i] += frame[i];
    }
  }
  for (let i = 0; i < 12; i++) {
    avgChroma[i] /= chromaFrames.length;
  }

  let bestKey = null;
  let bestCorr = -1;

  // Test all major and minor keys
  for (let i = 0; i < 12; i++) {
    // Rotate chroma to align with key
    const rotatedChroma = [];
    for (let j = 0; j < 12; j++) {
      rotatedChroma.push(avgChroma[(j + i) % 12]);
    }

    // Correlate with major profile
    const majorCorr = correlation(rotatedChroma, MAJOR_PROFILE);
    if (majorCorr > bestCorr) {
      bestCorr = majorCorr;
      bestKey = `${PITCH_CLASSES[i]} major`;
    }

    // Correlate with minor profile
    const minorCorr = correlation(rotatedChroma, MINOR_PROFILE);
    if (minorCorr > bestCorr) {
      bestCorr = minorCorr;
      bestKey = `${PITCH_CLASSES[i]} minor`;
    }
  }

  // Convert correlation to confidence (0-1 range)
  const confidence = Math.max(0, Math.min(1, (bestCorr + 1) / 2));

  return { key: bestKey, confidence };
}

// Pearson correlation coefficient
function correlation(a, b) {
  const n = a.length;
  let sumA = 0, sumB = 0, sumAB = 0, sumA2 = 0, sumB2 = 0;

  for (let i = 0; i < n; i++) {
    sumA += a[i];
    sumB += b[i];
    sumAB += a[i] * b[i];
    sumA2 += a[i] * a[i];
    sumB2 += b[i] * b[i];
  }

  const num = n * sumAB - sumA * sumB;
  const den = Math.sqrt((n * sumA2 - sumA * sumA) * (n * sumB2 - sumB * sumB));

  return den === 0 ? 0 : num / den;
}

// Detect chords in a segment
function detectChords(audioBuffer, startTime, endTime, beatsPerMeasure, beatsToGroup) {
  const sampleRate = audioBuffer.sampleRate;

  // Detect tempo
  const tempo = detectTempo(audioBuffer, sampleRate);
  console.log('Detected tempo:', tempo, 'BPM');

  // Map time signature to pulse level
  let pulsesPerMeasure;
  if (beatsPerMeasure === 6) pulsesPerMeasure = 2;
  else if (beatsPerMeasure === 9) pulsesPerMeasure = 3;
  else if (beatsPerMeasure === 12) pulsesPerMeasure = 4;
  else pulsesPerMeasure = beatsPerMeasure;

  // Calculate measure duration
  const measureDuration = (60.0 / tempo) * pulsesPerMeasure;
  const intervalDuration = measureDuration * (beatsToGroup / beatsPerMeasure);

  console.log('Interval duration:', intervalDuration, 'seconds');

  // Create fixed-interval boundaries
  const duration = endTime - startTime;
  const intervals = [];
  for (let t = 0; t < duration; t += intervalDuration) {
    intervals.push({
      start: startTime + t,
      end: Math.min(startTime + t + intervalDuration, endTime)
    });
  }

  // Detect chord for each interval
  const chords = [];
  const hopSize = 1024;

  for (const interval of intervals) {
    const chromaFrames = extractChroma(audioBuffer, interval.start, interval.end, hopSize);

    if (chromaFrames.length === 0) continue;

    // Average chroma for this interval
    const avgChroma = new Array(12).fill(0);
    for (const frame of chromaFrames) {
      for (let i = 0; i < 12; i++) {
        avgChroma[i] += frame[i];
      }
    }

    // Normalize
    const norm = Math.sqrt(avgChroma.reduce((sum, v) => sum + v * v, 0)) + 1e-10;
    for (let i = 0; i < 12; i++) {
      avgChroma[i] /= norm;
    }

    // Find best matching chord
    let bestChord = null;
    let bestScore = -1;

    for (const [name, template] of Object.entries(CHORD_TEMPLATES)) {
      const templateNorm = Math.sqrt(template.reduce((sum, v) => sum + v * v, 0)) + 1e-10;
      const normalizedTemplate = template.map(v => v / templateNorm);

      const score = avgChroma.reduce((sum, v, i) => sum + v * normalizedTemplate[i], 0);

      if (score > bestScore) {
        bestScore = score;
        bestChord = name;
      }
    }

    // Only include if confidence is reasonable
    if (bestScore > 0.5) {
      chords.push({
        start: Math.round(interval.start * 100) / 100,
        end: Math.round(interval.end * 100) / 100,
        chord: bestChord
      });
    }
  }

  return chords;
}

// Main analysis function
async function analyzeAudio(audioBuffer, startTime, endTime, beatsPerMeasure, beatsToGroup) {
  // Set Meyda's sample rate
  Meyda.sampleRate = audioBuffer.sampleRate;
  Meyda.bufferSize = 2048;

  // Extract chroma for key detection
  const chromaFrames = extractChroma(audioBuffer, startTime, endTime);

  // Detect key
  const keyResult = detectKey(chromaFrames);

  // Detect chords
  const chords = detectChords(audioBuffer, startTime, endTime, beatsPerMeasure, beatsToGroup);

  return {
    key: keyResult.key,
    confidence: keyResult.confidence,
    chords: chords
  };
}

// WaveSurfer initialization
function initWaveSurfer(audioUrl) {
  if (wavesurfer) {
    wavesurfer.destroy();
  }

  wavesurfer = WaveSurfer.create({
    container: waveformContainer,
    waveColor: '#4a5568',
    progressColor: '#e94560',
    cursorColor: '#e94560',
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    height: 128,
    normalize: true,
  });

  regions = wavesurfer.registerPlugin(WaveSurfer.Regions.create());

  wavesurfer.on('ready', () => {
    durationEl.textContent = formatTime(wavesurfer.getDuration());
    const duration = wavesurfer.getDuration();
    const regionEnd = Math.min(10, duration);
    currentRegion = regions.addRegion({
      start: 0,
      end: regionEnd,
      color: 'rgba(233, 69, 96, 0.2)',
      drag: true,
      resize: true
    });
    updateSegmentDisplay();
    analyzeBtn.disabled = false;
    hideLoading();
  });

  wavesurfer.on('timeupdate', (time) => {
    currentTimeEl.textContent = formatTime(time);
    updateActiveChord(time);
  });

  wavesurfer.on('play', () => {
    playIcon.classList.add('hidden');
    pauseIcon.classList.remove('hidden');
  });

  wavesurfer.on('pause', () => {
    playIcon.classList.remove('hidden');
    pauseIcon.classList.add('hidden');
  });

  wavesurfer.on('error', (err) => {
    console.error('WaveSurfer error:', err);
    hideLoading();
    alert(`Error loading audio: ${err}`);
  });

  regions.on('region-updated', (region) => {
    currentRegion = region;
    updateSegmentDisplay();
  });

  regions.on('region-created', (region) => {
    regions.getRegions().forEach(r => {
      if (r !== region) r.remove();
    });
    currentRegion = region;
    updateSegmentDisplay();
  });

  regions.enableDragSelection({
    color: 'rgba(233, 69, 96, 0.2)'
  });

  wavesurfer.load(audioUrl);
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function updateSegmentDisplay() {
  if (currentRegion) {
    segmentStartEl.textContent = formatTime(currentRegion.start);
    segmentEndEl.textContent = formatTime(currentRegion.end);
  }
}

function updateActiveChord(time) {
  if (!currentChords.length || !chordElements.length || !chordCarousel) return;

  let activeIndex = -1;
  for (let i = 0; i < currentChords.length; i++) {
    const chordStart = currentChords[i].start;
    const chordEnd = currentChords[i].end || (currentChords[i + 1]?.start) || (chordStart + 10);

    if (time >= chordStart && time < chordEnd) {
      activeIndex = i;
      break;
    }
  }

  lastActiveChordIndex = activeIndex;

  chordElements.forEach((el, i) => {
    if (i === activeIndex) {
      el.classList.add('chord-item-active');
    } else {
      el.classList.remove('chord-item-active');
    }
  });

  if (activeIndex >= 0) {
    scrollCarouselToIndex(activeIndex);
  }
}

function scrollCarouselToIndex(index) {
  if (!chordCarousel || !chordElements[index]) return;

  const container = chordTimeline;
  const element = chordElements[index];

  const containerWidth = container.offsetWidth;
  const elementOffset = element.offsetLeft;
  const elementWidth = element.offsetWidth;

  const scrollOffset = elementOffset - (containerWidth / 2) + (elementWidth / 2);

  currentScrollOffset = scrollOffset;
  chordCarousel.style.transform = `translateX(${-scrollOffset}px)`;
}

function setCarouselOffset(offset) {
  if (!chordCarousel) return;

  const maxOffset = chordCarousel.scrollWidth - chordTimeline.offsetWidth;
  offset = Math.max(0, Math.min(offset, maxOffset));

  currentScrollOffset = offset;
  chordCarousel.style.transform = `translateX(${-offset}px)`;
}

function handleCarouselMouseDown(e) {
  isDragging = true;
  dragStartX = e.clientX;
  dragStartScrollOffset = currentScrollOffset;
  dragDistance = 0;
  chordCarousel.style.transition = 'none';
}

function handleCarouselMouseMove(e) {
  if (!isDragging) return;

  const deltaX = dragStartX - e.clientX;
  dragDistance = Math.abs(deltaX);
  setCarouselOffset(dragStartScrollOffset + deltaX);
}

function handleCarouselMouseUp() {
  if (!isDragging) return;

  isDragging = false;
  chordCarousel.style.transition = '';
}

function handleCarouselMouseLeave() {
  if (isDragging) {
    handleCarouselMouseUp();
  }
}

function wasDragging() {
  return dragDistance > 5;
}

function setupCarouselDrag() {
  if (!chordCarousel) return;

  chordTimeline.addEventListener('mousedown', handleCarouselMouseDown);
  document.addEventListener('mousemove', handleCarouselMouseMove);
  document.addEventListener('mouseup', handleCarouselMouseUp);
  chordTimeline.addEventListener('mouseleave', handleCarouselMouseLeave);
}

function cleanupCarouselDrag() {
  chordTimeline.removeEventListener('mousedown', handleCarouselMouseDown);
  document.removeEventListener('mousemove', handleCarouselMouseMove);
  document.removeEventListener('mouseup', handleCarouselMouseUp);
  chordTimeline.removeEventListener('mouseleave', handleCarouselMouseLeave);
}

function showLoading(text) {
  loadingText.textContent = text;
  loadingOverlay.classList.remove('hidden');
}

function hideLoading() {
  loadingOverlay.classList.add('hidden');
}

// Load audio file
async function loadFile(file) {
  currentFile = file;
  showLoading('Loading audio...');

  try {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    const arrayBuffer = await file.arrayBuffer();
    currentAudioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    // Create blob URL for wavesurfer
    const blob = new Blob([arrayBuffer], { type: file.type });
    const audioUrl = URL.createObjectURL(blob);

    initWaveSurfer(audioUrl);

    dropZone.classList.add('hidden');
    waveformSection.classList.remove('hidden');
    fileName.textContent = file.name;
  } catch (error) {
    hideLoading();
    alert(`Error loading file: ${error.message}`);
    console.error(error);
  }
}

function getGranularityInfo(sliderValue, beatsPerMeasure) {
  const settings = {
    1: { beats: 1, label: 'every beat' },
    2: { beats: Math.max(1, Math.floor(beatsPerMeasure / 2)), label: 'half measure' },
    3: { beats: beatsPerMeasure, label: '1 measure' },
    4: { beats: beatsPerMeasure * 2, label: '2 measures' },
    5: { beats: beatsPerMeasure * 4, label: '4 measures' }
  };
  return settings[sliderValue] || settings[3];
}

function updateGranularityLabel() {
  const beatsPerMeasure = parseInt(timeSignatureSelect.value, 10);
  const info = getGranularityInfo(parseInt(granularitySlider.value, 10), beatsPerMeasure);
  granularityValue.textContent = info.label;
}

async function analyzeSegment() {
  if (!currentRegion || !currentAudioBuffer) return;

  showLoading('Analyzing audio segment...');
  resultsSection.classList.add('hidden');

  const beatsPerMeasure = parseInt(timeSignatureSelect.value, 10);
  const granularity = getGranularityInfo(parseInt(granularitySlider.value, 10), beatsPerMeasure);
  const beatsToGroup = granularity.beats;

  try {
    const result = await analyzeAudio(
      currentAudioBuffer,
      currentRegion.start,
      currentRegion.end,
      beatsPerMeasure,
      beatsToGroup
    );

    displayResults(result);

    if (wavesurfer && currentRegion) {
      wavesurfer.seekTo(currentRegion.start / wavesurfer.getDuration());
    }

    hideLoading();
  } catch (error) {
    hideLoading();
    alert(`Analysis failed: ${error.message}`);
    console.error(error);
  }
}

function displayResults(result) {
  detectedKey.textContent = result.key || 'Unknown';

  const confidence = (result.confidence || 0) * 100;
  keyConfidence.style.width = `${confidence}%`;
  keyConfidenceText.textContent = `${Math.round(confidence)}% confidence`;

  chordTimeline.innerHTML = '';
  currentChords = result.chords || [];
  chordElements = [];
  chordCarousel = null;

  lastActiveChordIndex = -1;

  if (result.chords && result.chords.length > 0) {
    chordCarousel = document.createElement('div');
    chordCarousel.className = 'chord-carousel';
    chordTimeline.appendChild(chordCarousel);

    result.chords.forEach((chord, index) => {
      const chordEl = document.createElement('div');
      chordEl.className = 'chord-item';

      const notes = ChordSynth.getNoteNames(chord.chord);
      const notesHtml = notes.map((note, i) =>
        `<span class="chord-note ${i === 0 ? 'chord-note-root' : ''}">${note}</span>`
      ).join('');

      const fingering = getMandolinFingering(chord.chord);
      const tabHtml = renderMandolinTab(fingering);

      const romanNumeral = getRomanNumeral(chord.chord, result.key);
      const romanHtml = romanNumeral ? `<span class="chord-roman">${romanNumeral}</span>` : '';

      chordEl.innerHTML = `
        <span class="chord-name">${chord.chord}</span>
        ${romanHtml}
        <div class="chord-notes">${notesHtml}</div>
        ${tabHtml}
        <span class="chord-time">${formatTime(chord.start)}</span>
      `;

      chordEl.addEventListener('click', () => {
        if (wasDragging()) return;
        ChordSynth.play(chord.chord, 1.0);
        scrollCarouselToIndex(index);
        chordEl.style.transform = 'scale(1.05)';
        setTimeout(() => {
          chordEl.style.transform = '';
        }, 150);
      });
      chordEl.style.cursor = 'pointer';
      chordEl.title = 'Click to hear this chord';
      chordCarousel.appendChild(chordEl);
      chordElements.push(chordEl);
    });

    setupCarouselDrag();
    setTimeout(() => scrollCarouselToIndex(0), 100);
  } else {
    chordTimeline.innerHTML = '<p style="color: var(--text-muted);">No chords detected in this segment</p>';
  }

  resultsSection.classList.remove('hidden');
}

function clearCurrentFile() {
  if (wavesurfer) {
    wavesurfer.destroy();
    wavesurfer = null;
  }
  cleanupCarouselDrag();
  currentRegion = null;
  currentAudioBuffer = null;
  currentFile = null;
  currentChords = [];
  chordElements = [];
  chordCarousel = null;
  currentScrollOffset = 0;
  dragDistance = 0;
  lastActiveChordIndex = -1;

  waveformSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  dropZone.classList.remove('hidden');
  analyzeBtn.disabled = true;

  currentTimeEl.textContent = '0:00';
  durationEl.textContent = '0:00';
  segmentStartEl.textContent = '0:00';
  segmentEndEl.textContent = '0:00';
}

// Event Listeners

dropZone.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    loadFile(e.target.files[0]);
  }
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');

  if (e.dataTransfer.files.length > 0) {
    loadFile(e.dataTransfer.files[0]);
  }
});

playPause.addEventListener('click', () => {
  if (wavesurfer) {
    wavesurfer.playPause();
  }
});

analyzeBtn.addEventListener('click', analyzeSegment);

clearFile.addEventListener('click', clearCurrentFile);

presetButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const beats = btn.dataset.beats;
    timeSignatureSelect.value = beats;

    presetButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateGranularityLabel();
  });
});

timeSignatureSelect.addEventListener('change', () => {
  presetButtons.forEach(b => b.classList.remove('active'));
  updateGranularityLabel();
});

granularitySlider.addEventListener('input', updateGranularityLabel);

updateGranularityLabel();

document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;

  if (e.code === 'Space' && wavesurfer) {
    e.preventDefault();
    wavesurfer.playPause();
  }
});
