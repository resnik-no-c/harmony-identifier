# Harmony Identifier

A desktop app that detects chords and musical keys from audio and video files. Perfect for musicians learning songs by ear!

![Harmony Identifier Screenshot](https://img.shields.io/badge/Platform-macOS-blue)

## Features

- **Drag & drop** audio or video files
- **YouTube support** - paste any YouTube URL
- **Visual waveform** with segment selection
- **Chord detection** with confidence scores
- **Key detection** using music theory algorithms
- **Time signature presets** - Reel, Jig, Hornpipe, Waltz
- **Adjustable detail level** - from every beat to 4 measures
- **Mandolin fingering diagrams** for each chord
- **Roman numeral analysis** (I, IV, V, etc.)
- **Click any chord** to hear it played

---

## Installation Guide (Mac)

### Step 1: Install Homebrew (Package Manager)

Homebrew makes installing software easy. Open **Terminal** (search for "Terminal" in Spotlight) and paste this command:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Press Enter and follow the prompts. You may need to enter your Mac password.

**After installation**, Homebrew will show you commands to add it to your PATH. They look like this (copy the ones shown in YOUR terminal, not these):
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### Step 2: Install Required Software

In Terminal, run these commands one at a time:

```bash
brew install node
```

```bash
brew install python@3.11
```

```bash
brew install ffmpeg
```

Each command may take a few minutes. Wait for each to finish before running the next.

### Step 3: Download Harmony Identifier

**Option A: Download ZIP (Easiest)**

1. Go to: https://github.com/resnik-no-c/harmony-identifier
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Find the ZIP in your Downloads folder and double-click to unzip
5. Drag the `harmony-identifier-main` folder to your Desktop (or anywhere you like)

**Option B: Using Git (if you have it)**

```bash
cd ~/Desktop
git clone https://github.com/resnik-no-c/harmony-identifier.git
```

### Step 4: Set Up the App

Open Terminal and navigate to the folder. If you put it on your Desktop:

```bash
cd ~/Desktop/harmony-identifier-main
```

Or if you used git:

```bash
cd ~/Desktop/harmony-identifier
```

Now run the setup script:

```bash
./setup.sh
```

If you get "permission denied", run this first:
```bash
chmod +x setup.sh && ./setup.sh
```

The setup will:
- Install JavaScript dependencies
- Create a Python environment
- Install Python audio libraries

This may take 5-10 minutes. You'll see lots of text scrolling - that's normal!

### Step 5: Run the App

```bash
npm start
```

The app window should open! 🎉

---

## How to Use

### Loading Audio/Video Files

1. **Drag and drop** any audio or video file onto the app
2. Or **click** the drop zone to browse for files
3. Supported formats: MP3, WAV, M4A, FLAC, MP4, MOV, AVI, MKV

### Loading from YouTube

1. Copy a YouTube URL (e.g., `https://www.youtube.com/watch?v=...`)
2. Paste it into the YouTube field
3. Press Enter or click the arrow button
4. Wait for the download to complete

### Selecting a Segment

1. Click and drag on the waveform to select a section
2. The blue highlighted region is what will be analyzed
3. You can drag the edges to resize, or drag the middle to move it

### Analyzing

1. Choose a **time signature** (or click a preset like "Jig" or "Reel")
2. Adjust the **Detail** slider:
   - Left = more chords (every beat)
   - Right = fewer chords (grouped by measures)
3. Click **"Analyze Selection"**

### Reading Results

- **Detected Key** shows the musical key with confidence percentage
- **Chord cards** scroll as the audio plays
- **Click any chord** to hear it
- **Roman numerals** show the chord's role in the key (I, IV, V, etc.)
- **Mandolin tabs** show fingering for each chord

---

## Troubleshooting

### "command not found: npm"

Homebrew may not be in your PATH. Run:
```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Then try again.

### "command not found: python3"

Run:
```bash
brew install python@3.11
```

### Setup script fails with Python errors

Make sure you have Python 3.11:
```bash
python3 --version
```

If it shows Python 2.x or an error, run:
```bash
brew install python@3.11
brew link python@3.11
```

### YouTube download fails

Make sure you have the latest yt-dlp:
```bash
source python/venv/bin/activate
pip install --upgrade yt-dlp
```

### App won't start / white screen

Try reinstalling dependencies:
```bash
rm -rf node_modules
npm install
npm start
```

### "No chords detected"

- Try selecting a longer segment (at least 5-10 seconds)
- Make sure the audio has clear harmonic content (chords, not just drums)
- Try adjusting the Detail slider

---

## Running the App (After First Setup)

Once set up, you only need to run:

```bash
cd ~/Desktop/harmony-identifier-main
npm start
```

**Tip:** Create a shortcut! Save this as `Harmony.command` on your Desktop:

```bash
#!/bin/bash
cd ~/Desktop/harmony-identifier-main
npm start
```

Then make it executable:
```bash
chmod +x ~/Desktop/Harmony.command
```

Now you can double-click `Harmony.command` to launch the app!

---

## Updating the App

To get the latest version:

```bash
cd ~/Desktop/harmony-identifier-main
git pull
npm install
./setup.sh
```

---

## Credits

- Audio analysis: [librosa](https://librosa.org/), [madmom](https://madmom.readthedocs.io/)
- Waveform display: [wavesurfer.js](https://wavesurfer-js.org/)
- YouTube downloads: [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Desktop framework: [Electron](https://www.electronjs.org/)

---

## Web Version

A simplified browser-only version (no YouTube support) is available at:
https://resnik-no-c.github.io/harmony-identifier/

---

## License

MIT License - feel free to use, modify, and share!
