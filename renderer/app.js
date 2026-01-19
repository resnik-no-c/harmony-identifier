// DOM Elements
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const youtubeSection = document.getElementById('youtubeSection');
const youtubeUrl = document.getElementById('youtubeUrl');
const youtubeLoadBtn = document.getElementById('youtubeLoadBtn');
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
let currentAudioPath = null;
let originalFilePath = null;
let audioContext = null;
let currentChords = []; // Store chords for playback highlighting
let chordElements = []; // Store chord DOM elements
let chordCarousel = null; // Store carousel element for scrolling
let lastActiveChordIndex = -1; // Track last active chord for debug logging

// Carousel drag state
let isDragging = false;
let dragStartX = 0;
let dragStartScrollOffset = 0;
let currentScrollOffset = 0;
let dragDistance = 0; // Track total drag distance to differentiate from clicks

// Chord synthesizer using Web Audio API
const ChordSynth = {
  // Note frequencies (A4 = 440Hz)
  noteFrequencies: {
    'C': 261.63, 'C#': 277.18, 'Db': 277.18,
    'D': 293.66, 'D#': 311.13, 'Eb': 311.13,
    'E': 329.63,
    'F': 349.23, 'F#': 369.99, 'Gb': 369.99,
    'G': 392.00, 'G#': 415.30, 'Ab': 415.30,
    'A': 440.00, 'A#': 466.16, 'Bb': 466.16,
    'B': 493.88
  },

  // Parse chord name into root and quality
  parseChord(chordName) {
    // Handle various chord notations
    const match = chordName.match(/^([A-G][#b]?)(.*)/);
    if (!match) return null;

    const root = match[1];
    const quality = match[2].toLowerCase();

    return { root, quality };
  },

  // Get chord intervals based on quality
  getIntervals(quality) {
    // Semitone intervals from root
    if (quality.includes('dim')) return [0, 3, 6];       // Diminished
    if (quality.includes('aug')) return [0, 4, 8];       // Augmented
    if (quality.includes('m7') || quality.includes('min7')) return [0, 3, 7, 10]; // Minor 7th
    if (quality.includes('maj7')) return [0, 4, 7, 11];  // Major 7th
    if (quality.includes('7')) return [0, 4, 7, 10];     // Dominant 7th
    if (quality.includes('m') || quality.includes('min')) return [0, 3, 7]; // Minor
    return [0, 4, 7]; // Major (default)
  },

  // Get frequency for a note
  getFrequency(root, semitones) {
    const baseFreq = this.noteFrequencies[root];
    if (!baseFreq) return 440;
    return baseFreq * Math.pow(2, semitones / 12);
  },

  // Play a chord
  play(chordName, duration = 1.0) {
    const parsed = this.parseChord(chordName);
    if (!parsed) return;

    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }

    const intervals = this.getIntervals(parsed.quality);
    const now = audioContext.currentTime;

    // Create oscillators for each note in the chord
    intervals.forEach((semitones, i) => {
      const freq = this.getFrequency(parsed.root, semitones);

      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();

      osc.type = 'triangle'; // Softer sound than sine
      osc.frequency.value = freq;

      // Envelope for natural sound
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(0.15, now + 0.05); // Attack
      gain.gain.exponentialRampToValueAtTime(0.1, now + 0.2); // Decay
      gain.gain.setValueAtTime(0.1, now + duration - 0.1); // Sustain
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration); // Release

      osc.connect(gain);
      gain.connect(audioContext.destination);

      osc.start(now);
      osc.stop(now + duration);
    });
  },

  // Get note names for a chord
  getNoteNames(chordName) {
    const parsed = this.parseChord(chordName);
    if (!parsed) return [];

    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const rootIndex = noteNames.indexOf(parsed.root.replace('b', '#'));

    // Handle flats by converting to sharps for lookup
    let actualRootIndex = rootIndex;
    if (parsed.root.includes('b')) {
      const flatToSharp = { 'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#' };
      actualRootIndex = noteNames.indexOf(flatToSharp[parsed.root] || parsed.root);
    }

    const intervals = this.getIntervals(parsed.quality);
    return intervals.map(interval => {
      const noteIndex = (actualRootIndex + interval) % 12;
      return noteNames[noteIndex];
    });
  }
};

// Mandolin chord fingerings (strings: G-D-A-E from low to high)
// Format: [G-string fret, D-string fret, A-string fret, E-string fret]
// 'x' = muted, '0' = open
const MandolinChords = {
  // Major chords
  'C':  [0, 2, 3, 0],
  'C#': [1, 3, 4, 1], 'Db': [1, 3, 4, 1],
  'D':  [2, 0, 0, 2],
  'D#': [3, 1, 1, 3], 'Eb': [3, 1, 1, 3],
  'E':  [4, 2, 2, 0],
  'F':  [5, 3, 3, 1],
  'F#': [6, 4, 4, 2], 'Gb': [6, 4, 4, 2],
  'G':  [0, 0, 2, 3],
  'G#': [1, 1, 3, 4], 'Ab': [1, 1, 3, 4],
  'A':  [2, 2, 0, 0],
  'A#': [3, 3, 1, 1], 'Bb': [3, 3, 1, 1],
  'B':  [4, 4, 2, 2],

  // Minor chords
  'Cm':  [0, 1, 3, 0],
  'C#m': [1, 2, 4, 1], 'Dbm': [1, 2, 4, 1],
  'Dm':  [2, 0, 0, 1],
  'D#m': [3, 1, 1, 2], 'Ebm': [3, 1, 1, 2],
  'Em':  [0, 2, 2, 0],
  'Fm':  [1, 3, 3, 1],
  'F#m': [2, 4, 4, 2], 'Gbm': [2, 4, 4, 2],
  'Gm':  [0, 0, 1, 3],
  'G#m': [1, 1, 2, 4], 'Abm': [1, 1, 2, 4],
  'Am':  [2, 2, 0, 0],
  'A#m': [3, 3, 1, 1], 'Bbm': [3, 3, 1, 1],
  'Bm':  [4, 4, 2, 2],

  // 7th chords
  'C7':  [0, 2, 3, 3],
  'D7':  [2, 0, 0, 1],
  'E7':  [4, 2, 2, 3],
  'F7':  [5, 3, 3, 4],
  'G7':  [0, 0, 2, 1],
  'A7':  [2, 2, 0, 3],
  'B7':  [4, 4, 2, 0],

  // Minor 7th chords
  'Cm7':  [0, 1, 3, 3],
  'Dm7':  [2, 0, 0, 0],
  'Em7':  [0, 2, 2, 3],
  'Am7':  [2, 2, 0, 3],
};

// Get mandolin fingering for a chord
function getMandolinFingering(chordName) {
  // Try exact match first
  if (MandolinChords[chordName]) {
    return MandolinChords[chordName];
  }

  // Try parsing and simplifying
  const parsed = ChordSynth.parseChord(chordName);
  if (!parsed) return null;

  // Try root + simple quality
  const simpleChord = parsed.root + (parsed.quality.includes('m') && !parsed.quality.includes('maj') ? 'm' : '');
  if (MandolinChords[simpleChord]) {
    return MandolinChords[simpleChord];
  }

  // Try just the root (major)
  if (MandolinChords[parsed.root]) {
    return MandolinChords[parsed.root];
  }

  return null;
}

// Render mandolin tab as HTML
function renderMandolinTab(fingering) {
  if (!fingering) {
    return '<div class="mando-tab mando-tab-unknown">?</div>';
  }

  const strings = ['E', 'A', 'D', 'G']; // Display order (high to low)
  const frets = [...fingering].reverse(); // Reverse to match display order

  let html = '<div class="mando-tab">';
  html += '<div class="mando-strings">';

  for (let i = 0; i < 4; i++) {
    const fret = frets[i];
    const fretDisplay = fret === 'x' ? 'x' : fret;
    html += `<div class="mando-string">
      <span class="mando-string-name">${strings[i]}</span>
      <span class="mando-fret">${fretDisplay}</span>
    </div>`;
  }

  html += '</div></div>';
  return html;
}

// Get Roman numeral interval for a chord relative to the key
function getRomanNumeral(chordName, keyName) {
  if (!chordName || !keyName) return null;

  const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
  const romanNumerals = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'];

  // Parse the key (e.g., "A major" or "F# minor")
  const keyMatch = keyName.match(/^([A-G][#b]?)\s*(major|minor)?/i);
  if (!keyMatch) return null;

  let keyRoot = keyMatch[1];
  const keyMode = (keyMatch[2] || 'major').toLowerCase();

  // Parse the chord
  const chordParsed = ChordSynth.parseChord(chordName);
  if (!chordParsed) return null;

  let chordRoot = chordParsed.root;
  const chordQuality = chordParsed.quality;

  // Convert flats to sharps for comparison
  const flatToSharp = { 'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#' };
  if (flatToSharp[keyRoot]) keyRoot = flatToSharp[keyRoot];
  if (flatToSharp[chordRoot]) chordRoot = flatToSharp[chordRoot];

  // Get indices
  const keyIndex = noteNames.indexOf(keyRoot);
  const chordIndex = noteNames.indexOf(chordRoot);
  if (keyIndex === -1 || chordIndex === -1) return null;

  // Calculate interval (semitones from key root)
  const interval = (chordIndex - keyIndex + 12) % 12;

  // Map semitones to scale degrees
  // Major scale intervals: 0, 2, 4, 5, 7, 9, 11
  // Minor scale intervals: 0, 2, 3, 5, 7, 8, 10
  const majorIntervals = { 0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6 };
  const minorIntervals = { 0: 0, 2: 1, 3: 2, 5: 3, 7: 4, 8: 5, 10: 6 };

  const scaleIntervals = keyMode === 'minor' ? minorIntervals : majorIntervals;
  let degree = scaleIntervals[interval];

  // Handle non-diatonic chords (chromatic alterations)
  let prefix = '';
  let suffix = '';

  if (degree === undefined) {
    // Find closest scale degree
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
      // Fallback: just show the interval
      degree = Math.round(interval / 2);
    }
  }

  // Get the Roman numeral
  let numeral = romanNumerals[degree] || '?';

  // Determine if chord is major or minor and set case accordingly
  const isMinorChord = chordQuality.includes('m') && !chordQuality.includes('maj');
  const isDimChord = chordQuality.includes('dim');
  const isAugChord = chordQuality.includes('aug');

  if (isMinorChord || isDimChord) {
    numeral = numeral.toLowerCase();
  }

  // Add chord quality symbols
  if (isDimChord) suffix = '°';
  else if (isAugChord) suffix = '+';
  else if (chordQuality.includes('7')) {
    if (chordQuality.includes('maj7')) suffix = 'maj7';
    else if (chordQuality.includes('m7') || chordQuality.includes('min7')) suffix = '7';
    else suffix = '7';
  }

  return prefix + numeral + suffix;
}

// Initialize WaveSurfer with pre-generated peaks
function initWaveSurfer(audioUrl, peaks, duration) {
  if (wavesurfer) {
    wavesurfer.destroy();
  }

  // Create an audio element for playback
  const audio = new Audio();
  audio.src = audioUrl;

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
    media: audio,
    peaks: [peaks],  // Pre-generated peaks - no browser decoding needed
    duration: duration
  });

  // Initialize regions plugin
  regions = wavesurfer.registerPlugin(WaveSurfer.Regions.create());

  // Event listeners
  wavesurfer.on('ready', () => {
    durationEl.textContent = formatTime(wavesurfer.getDuration());
    // Create initial region covering first 10 seconds or full duration
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

  // Region events
  regions.on('region-updated', (region) => {
    currentRegion = region;
    updateSegmentDisplay();
  });

  regions.on('region-created', (region) => {
    // Remove previous regions, keep only one
    regions.getRegions().forEach(r => {
      if (r !== region) r.remove();
    });
    currentRegion = region;
    updateSegmentDisplay();
  });

  // Allow creating new regions by clicking on waveform
  regions.enableDragSelection({
    color: 'rgba(233, 69, 96, 0.2)'
  });
}

// Format time in M:SS format
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Update segment display
function updateSegmentDisplay() {
  if (currentRegion) {
    segmentStartEl.textContent = formatTime(currentRegion.start);
    segmentEndEl.textContent = formatTime(currentRegion.end);
  }
}

// Timing offset to compensate for audio analysis latency (adjust if chords are early/late)
const CHORD_TIMING_OFFSET = 0; // seconds - positive = chords trigger later, negative = earlier

// Update active chord based on playback time
function updateActiveChord(time) {
  if (!currentChords.length || !chordElements.length || !chordCarousel) return;

  // Apply timing offset for analysis latency compensation
  const adjustedTime = time + CHORD_TIMING_OFFSET;

  // Find which chord is active at this time
  let activeIndex = -1;
  for (let i = 0; i < currentChords.length; i++) {
    const chordStart = currentChords[i].start;
    // Use the next chord's start as end time, or segment end, or a reasonable default
    const chordEnd = currentChords[i].end || (currentChords[i + 1]?.start) || (chordStart + 10);

    if (adjustedTime >= chordStart && adjustedTime < chordEnd) {
      activeIndex = i;
      break;
    }
  }

  // Track active chord changes
  lastActiveChordIndex = activeIndex;

  // Update active class on chord elements
  chordElements.forEach((el, i) => {
    if (i === activeIndex) {
      el.classList.add('chord-item-active');
    } else {
      el.classList.remove('chord-item-active');
    }
  });

  // Scroll carousel to center the active chord
  if (activeIndex >= 0) {
    scrollCarouselToIndex(activeIndex);
  }
}

// Scroll carousel to center a specific chord index
function scrollCarouselToIndex(index) {
  if (!chordCarousel || !chordElements[index]) return;

  const carousel = chordCarousel;
  const container = chordTimeline;
  const element = chordElements[index];

  // Calculate the offset to center this element
  const containerWidth = container.offsetWidth;
  const elementOffset = element.offsetLeft;
  const elementWidth = element.offsetWidth;

  // Center the element in the container
  const scrollOffset = elementOffset - (containerWidth / 2) + (elementWidth / 2);

  currentScrollOffset = scrollOffset;
  carousel.style.transform = `translateX(${-scrollOffset}px)`;
}

// Set carousel scroll offset directly (for dragging)
function setCarouselOffset(offset) {
  if (!chordCarousel) return;

  // Clamp the offset to valid range
  const maxOffset = chordCarousel.scrollWidth - chordTimeline.offsetWidth;
  offset = Math.max(0, Math.min(offset, maxOffset));

  currentScrollOffset = offset;
  chordCarousel.style.transform = `translateX(${-offset}px)`;
}

// Carousel drag handlers
function handleCarouselMouseDown(e) {
  isDragging = true;
  dragStartX = e.clientX;
  dragStartScrollOffset = currentScrollOffset;
  dragDistance = 0;
  chordCarousel.style.transition = 'none'; // Disable smooth transition while dragging
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
  chordCarousel.style.transition = ''; // Re-enable smooth transition
}

function handleCarouselMouseLeave() {
  if (isDragging) {
    handleCarouselMouseUp();
  }
}

// Check if the last interaction was a drag (vs a click)
function wasDragging() {
  return dragDistance > 5; // 5px threshold
}

// Set up carousel drag events
function setupCarouselDrag() {
  if (!chordCarousel) return;

  chordTimeline.addEventListener('mousedown', handleCarouselMouseDown);
  document.addEventListener('mousemove', handleCarouselMouseMove);
  document.addEventListener('mouseup', handleCarouselMouseUp);
  chordTimeline.addEventListener('mouseleave', handleCarouselMouseLeave);
}

// Clean up carousel drag events
function cleanupCarouselDrag() {
  chordTimeline.removeEventListener('mousedown', handleCarouselMouseDown);
  document.removeEventListener('mousemove', handleCarouselMouseMove);
  document.removeEventListener('mouseup', handleCarouselMouseUp);
  chordTimeline.removeEventListener('mouseleave', handleCarouselMouseLeave);
}

// Show loading overlay
function showLoading(text) {
  loadingText.textContent = text;
  loadingOverlay.classList.remove('hidden');
}

// Hide loading overlay
function hideLoading() {
  loadingOverlay.classList.add('hidden');
}

// Load audio file
async function loadFile(filePath) {
  originalFilePath = filePath;
  showLoading('Loading file...');

  try {
    // Check if it's a video file
    const isVideo = await window.electronAPI.isVideoFile(filePath);

    if (isVideo) {
      showLoading('Extracting audio from video...');
      const result = await window.electronAPI.extractAudio(filePath);
      currentAudioPath = result.audioPath;
    } else {
      currentAudioPath = filePath;
    }

    // Generate peaks server-side to avoid browser crash
    showLoading('Generating waveform...');
    const peaksResult = await window.electronAPI.generatePeaks(currentAudioPath);
    if (!peaksResult.success) {
      throw new Error(peaksResult.error || 'Failed to generate waveform');
    }
    console.log('Peaks generated:', peaksResult.peaks.length, 'points');

    // Get file URL and initialize wavesurfer with pre-generated peaks
    const fileUrl = await window.electronAPI.getFileUrl(currentAudioPath);
    console.log('Loading audio from:', fileUrl);

    initWaveSurfer(fileUrl, peaksResult.peaks, peaksResult.duration);
    console.log('Wavesurfer initialized with peaks');

    // Show waveform section, hide drop zone and youtube section
    dropZone.classList.add('hidden');
    youtubeSection.classList.add('hidden');
    waveformSection.classList.remove('hidden');
    fileName.textContent = filePath.split('/').pop();

    hideLoading();
  } catch (error) {
    hideLoading();
    alert(`Error loading file: ${error.message}`);
    console.error(error);
  }
}

// Load audio from YouTube URL
async function loadFromYouTube(url) {
  if (!url || !url.trim()) {
    alert('Please enter a YouTube URL');
    return;
  }

  showLoading('Downloading audio from YouTube...');

  try {
    const result = await window.electronAPI.downloadYoutube(url.trim());

    if (!result.success) {
      throw new Error(result.error || 'Download failed');
    }

    currentAudioPath = result.audioPath;
    originalFilePath = url;

    // Generate peaks server-side to avoid browser crash
    showLoading('Generating waveform...');
    const peaksResult = await window.electronAPI.generatePeaks(currentAudioPath);
    if (!peaksResult.success) {
      throw new Error(peaksResult.error || 'Failed to generate waveform');
    }
    console.log('Peaks generated:', peaksResult.peaks.length, 'points');

    // Get file URL and initialize wavesurfer with pre-generated peaks
    const fileUrl = await window.electronAPI.getFileUrl(currentAudioPath);
    console.log('Loading audio from:', fileUrl);

    initWaveSurfer(fileUrl, peaksResult.peaks, peaksResult.duration);
    console.log('Wavesurfer initialized with peaks');

    // Show waveform section, hide drop zone and youtube section
    dropZone.classList.add('hidden');
    youtubeSection.classList.add('hidden');
    waveformSection.classList.remove('hidden');
    fileName.textContent = result.title || 'YouTube Audio';
    console.log('UI updated, waveformSection visible:', !waveformSection.classList.contains('hidden'));

    // Clear the input
    youtubeUrl.value = '';

    hideLoading();
    console.log('Loading hidden');
  } catch (error) {
    hideLoading();
    // Restore UI on error
    dropZone.classList.remove('hidden');
    youtubeSection.classList.remove('hidden');
    waveformSection.classList.add('hidden');
    alert(`Error loading from YouTube: ${error.message}`);
    console.error(error);
  }
}

// Get granularity settings based on slider value
function getGranularityInfo(sliderValue, beatsPerMeasure) {
  // Slider values 1-5 map to different groupings
  const settings = {
    1: { beats: 1, label: 'every beat' },
    2: { beats: Math.max(1, Math.floor(beatsPerMeasure / 2)), label: 'half measure' },
    3: { beats: beatsPerMeasure, label: '1 measure' },
    4: { beats: beatsPerMeasure * 2, label: '2 measures' },
    5: { beats: beatsPerMeasure * 4, label: '4 measures' }
  };
  return settings[sliderValue] || settings[3];
}

// Update granularity label when slider changes
function updateGranularityLabel() {
  const beatsPerMeasure = parseInt(timeSignatureSelect.value, 10);
  const info = getGranularityInfo(parseInt(granularitySlider.value, 10), beatsPerMeasure);
  granularityValue.textContent = info.label;
}

// Analyze selected segment
async function analyzeSegment() {
  if (!currentRegion || !currentAudioPath) return;

  showLoading('Analyzing audio segment...');
  resultsSection.classList.add('hidden');

  // Get selected beats per measure from time signature dropdown
  const beatsPerMeasure = parseInt(timeSignatureSelect.value, 10);

  // Get granularity (how many beats to group for each chord)
  const granularity = getGranularityInfo(parseInt(granularitySlider.value, 10), beatsPerMeasure);
  const beatsToGroup = granularity.beats;

  try {
    const result = await window.electronAPI.analyzeAudio(
      currentAudioPath,
      currentRegion.start,
      currentRegion.end,
      beatsPerMeasure,
      beatsToGroup
    );

    displayResults(result);

    // Seek to start of analyzed region so playback aligns with chords
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

// Display analysis results
function displayResults(result) {
  // Display key
  detectedKey.textContent = result.key || 'Unknown';

  // Display confidence
  const confidence = (result.confidence || 0) * 100;
  keyConfidence.style.width = `${confidence}%`;
  keyConfidenceText.textContent = `${Math.round(confidence)}% confidence`;

  // Display chords
  chordTimeline.innerHTML = '';
  currentChords = result.chords || [];
  chordElements = [];
  chordCarousel = null;

  lastActiveChordIndex = -1; // Reset for new analysis

  if (result.chords && result.chords.length > 0) {
    // Create carousel container
    chordCarousel = document.createElement('div');
    chordCarousel.className = 'chord-carousel';
    chordTimeline.appendChild(chordCarousel);

    result.chords.forEach((chord, index) => {
      const chordEl = document.createElement('div');
      chordEl.className = 'chord-item';

      // Get chord notes
      const notes = ChordSynth.getNoteNames(chord.chord);
      const notesHtml = notes.map((note, i) =>
        `<span class="chord-note ${i === 0 ? 'chord-note-root' : ''}">${note}</span>`
      ).join('');

      // Get mandolin fingering
      const fingering = getMandolinFingering(chord.chord);
      const tabHtml = renderMandolinTab(fingering);

      // Get Roman numeral interval
      const romanNumeral = getRomanNumeral(chord.chord, result.key);
      const romanHtml = romanNumeral ? `<span class="chord-roman">${romanNumeral}</span>` : '';

      chordEl.innerHTML = `
        <span class="chord-name">${chord.chord}</span>
        ${romanHtml}
        <div class="chord-notes">${notesHtml}</div>
        ${tabHtml}
        <span class="chord-time">${formatTime(chord.start)}</span>
      `;

      // Add click handler to play the chord and scroll to it
      chordEl.addEventListener('click', () => {
        // Ignore if this was a drag, not a click
        if (wasDragging()) return;

        ChordSynth.play(chord.chord, 1.0);
        scrollCarouselToIndex(index);
        // Visual feedback
        chordEl.style.transform = 'scale(1.05)';
        setTimeout(() => {
          chordEl.style.transform = '';
        }, 150);
      });
      chordEl.style.cursor = 'pointer';
      chordEl.title = 'Click to hear this chord';
      chordCarousel.appendChild(chordEl);
      chordElements.push(chordEl); // Store reference for highlighting
    });

    // Set up drag functionality and center on first chord
    setupCarouselDrag();
    setTimeout(() => scrollCarouselToIndex(0), 100);
  } else {
    chordTimeline.innerHTML = '<p style="color: var(--text-muted);">No chords detected in this segment</p>';
  }

  resultsSection.classList.remove('hidden');
}

// Clear current file
function clearCurrentFile() {
  if (wavesurfer) {
    wavesurfer.destroy();
    wavesurfer = null;
  }
  cleanupCarouselDrag();
  currentRegion = null;
  currentAudioPath = null;
  originalFilePath = null;
  currentChords = [];
  chordElements = [];
  chordCarousel = null;
  currentScrollOffset = 0;
  dragDistance = 0;
  lastActiveChordIndex = -1;

  waveformSection.classList.add('hidden');
  resultsSection.classList.add('hidden');
  dropZone.classList.remove('hidden');
  youtubeSection.classList.remove('hidden');
  analyzeBtn.disabled = true;

  currentTimeEl.textContent = '0:00';
  durationEl.textContent = '0:00';
  segmentStartEl.textContent = '0:00';
  segmentEndEl.textContent = '0:00';
}

// Event Listeners

// Drop zone click
dropZone.addEventListener('click', async () => {
  const filePath = await window.electronAPI.openFileDialog();
  if (filePath) {
    loadFile(filePath);
  }
});

// File input change (fallback)
fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    loadFile(e.target.files[0].path);
  }
});

// Drag and drop
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
    loadFile(e.dataTransfer.files[0].path);
  }
});

// Play/Pause button
playPause.addEventListener('click', () => {
  if (wavesurfer) {
    wavesurfer.playPause();
  }
});

// Analyze button
analyzeBtn.addEventListener('click', analyzeSegment);

// Clear file button
clearFile.addEventListener('click', clearCurrentFile);

// YouTube load button
youtubeLoadBtn.addEventListener('click', () => {
  loadFromYouTube(youtubeUrl.value);
});

// YouTube URL input - load on Enter key
youtubeUrl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    loadFromYouTube(youtubeUrl.value);
  }
});

// Time signature preset buttons
presetButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    const beats = btn.dataset.beats;
    timeSignatureSelect.value = beats;

    // Update active state on buttons
    presetButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// Clear active preset when dropdown changes manually
timeSignatureSelect.addEventListener('change', () => {
  presetButtons.forEach(b => b.classList.remove('active'));
  updateGranularityLabel(); // Update label since beats per measure changed
});

// Granularity slider
granularitySlider.addEventListener('input', updateGranularityLabel);

// Initialize granularity label
updateGranularityLabel();

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  // Don't trigger space shortcut when typing in input fields
  if (e.target.tagName === 'INPUT') return;

  if (e.code === 'Space' && wavesurfer) {
    e.preventDefault();
    wavesurfer.playPause();
  }
});
