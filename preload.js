const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Open file dialog and return selected file path
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),

  // Extract audio from video file, returns { success, audioPath } or error
  extractAudio: (filePath) => ipcRenderer.invoke('extract-audio', filePath),

  // Analyze audio segment for chords and key
  // Returns { chords: [...], key: "...", confidence: 0.0-1.0 }
  analyzeAudio: (audioPath, startTime, endTime, beatsPerMeasure = 4, beatsToGroup = 4) =>
    ipcRenderer.invoke('analyze-audio', audioPath, startTime, endTime, beatsPerMeasure, beatsToGroup),

  // Check if file is a video file (needs audio extraction)
  isVideoFile: (filePath) => ipcRenderer.invoke('is-video-file', filePath),

  // Get file URL for loading in wavesurfer
  getFileUrl: (filePath) => ipcRenderer.invoke('get-file-url', filePath),

  // Download audio from YouTube URL
  // Returns { success, audioPath, title, duration } or error
  downloadYoutube: (url) => ipcRenderer.invoke('download-youtube', url),

  // Generate waveform peaks from audio file (server-side to avoid browser crashes)
  // Returns { success, peaks: [...], duration } or error
  generatePeaks: (audioPath) => ipcRenderer.invoke('generate-peaks', audioPath)
});
