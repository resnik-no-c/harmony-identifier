const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;

// Get the Python executable path (uses virtual environment if available)
function getPythonPath() {
  const venvPython = path.join(__dirname, 'python', 'venv', 'bin', 'python3');
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  return 'python3';
}

// Create the main application window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#1a1a2e'
  });

  mainWindow.loadFile('renderer/index.html');

  // Open DevTools in development
  mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers

// Open file dialog
ipcMain.handle('open-file-dialog', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Audio/Video', extensions: ['mp3', 'wav', 'm4a', 'flac', 'ogg', 'mp4', 'mov', 'avi', 'mkv', 'webm'] }
    ]
  });

  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

// Extract audio from video file
ipcMain.handle('extract-audio', async (event, filePath) => {
  return new Promise((resolve, reject) => {
    const tempDir = os.tmpdir();
    const outputPath = path.join(tempDir, `harmony_${Date.now()}.wav`);

    const pythonScript = path.join(__dirname, 'python', 'extract_audio.py');
    const pythonPath = getPythonPath();

    const process = spawn(pythonPath, [pythonScript, filePath, outputPath]);

    let stdout = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          resolve({ success: true, audioPath: outputPath });
        }
      } else {
        reject(new Error(stderr || `Process exited with code ${code}`));
      }
    });

    process.on('error', (err) => {
      reject(err);
    });
  });
});

// Analyze audio segment for chords and key
ipcMain.handle('analyze-audio', async (event, audioPath, startTime, endTime, beatsPerMeasure = 4, beatsToGroup = 4) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'python', 'analyze.py');
    const pythonPath = getPythonPath();

    const process = spawn(pythonPath, [
      pythonScript,
      audioPath,
      startTime.toString(),
      endTime.toString(),
      beatsPerMeasure.toString(),
      beatsToGroup.toString()
    ]);

    let stdout = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse analysis result: ${e.message}`));
        }
      } else {
        reject(new Error(stderr || `Analysis failed with code ${code}`));
      }
    });

    process.on('error', (err) => {
      reject(err);
    });
  });
});

// Check if file is video type
ipcMain.handle('is-video-file', async (event, filePath) => {
  const videoExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'];
  const ext = path.extname(filePath).toLowerCase();
  return videoExtensions.includes(ext);
});

// Get audio file path (for direct loading in wavesurfer)
ipcMain.handle('get-file-url', async (event, filePath) => {
  return `file://${filePath}`;
});

// Generate waveform peaks from audio file (avoids browser-side decoding)
ipcMain.handle('generate-peaks', async (event, audioPath) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'python', 'generate_peaks.py');
    const pythonPath = getPythonPath();

    const process = spawn(pythonPath, [pythonScript, audioPath, '800']);

    let stdout = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse peaks result: ${e.message}`));
        }
      } else {
        reject(new Error(stderr || `Peaks generation failed with code ${code}`));
      }
    });

    process.on('error', (err) => {
      reject(err);
    });
  });
});

// Download audio from YouTube URL
ipcMain.handle('download-youtube', async (event, url) => {
  console.log('download-youtube called with URL:', url);
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'python', 'download_youtube.py');
    const pythonPath = getPythonPath();
    const tempDir = os.tmpdir();
    console.log('Python path:', pythonPath);
    console.log('Script path:', pythonScript);
    console.log('Temp dir:', tempDir);

    const process = spawn(pythonPath, [pythonScript, url, tempDir]);

    let stdout = '';
    let stderr = '';

    process.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    process.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    process.on('close', (code) => {
      console.log('YouTube download process exited with code:', code);
      console.log('stdout:', stdout);
      console.log('stderr:', stderr);
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse download result: ${e.message}`));
        }
      } else {
        // Try to parse error from stdout first (our script outputs JSON errors)
        try {
          const result = JSON.parse(stdout);
          reject(new Error(result.error || 'Download failed'));
        } catch (e) {
          reject(new Error(stderr || `Download failed with code ${code}`));
        }
      }
    });

    process.on('error', (err) => {
      console.log('YouTube download process error:', err);
      reject(err);
    });
  });
});
