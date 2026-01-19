#!/usr/bin/env python3
"""
Generate waveform peaks from audio file for visualization.
This avoids memory-intensive browser-side audio decoding.
"""

import sys
import json
import numpy as np
import librosa


def generate_peaks(audio_path: str, num_peaks: int = 800) -> dict:
    """
    Generate waveform peaks from an audio file.

    Args:
        audio_path: Path to audio file
        num_peaks: Number of peaks to generate (width of waveform)

    Returns:
        dict with peaks array and duration
    """
    try:
        # Load audio at lower sample rate for efficiency
        y, sr = librosa.load(audio_path, sr=22050, mono=True)
        duration = len(y) / sr

        # Calculate samples per peak
        samples_per_peak = len(y) // num_peaks
        if samples_per_peak < 1:
            samples_per_peak = 1
            num_peaks = len(y)

        # Generate peaks by taking max absolute value in each chunk
        peaks = []
        for i in range(num_peaks):
            start = i * samples_per_peak
            end = start + samples_per_peak
            chunk = y[start:end]
            if len(chunk) > 0:
                peak = float(np.max(np.abs(chunk)))
                peaks.append(peak)

        # Normalize peaks to 0-1 range
        max_peak = max(peaks) if peaks else 1
        if max_peak > 0:
            peaks = [p / max_peak for p in peaks]

        return {
            'success': True,
            'peaks': peaks,
            'duration': duration
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': 'Usage: generate_peaks.py <audio_path> [num_peaks]'
        }))
        sys.exit(1)

    audio_path = sys.argv[1]
    num_peaks = int(sys.argv[2]) if len(sys.argv) > 2 else 800

    result = generate_peaks(audio_path, num_peaks)
    print(json.dumps(result))

    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
