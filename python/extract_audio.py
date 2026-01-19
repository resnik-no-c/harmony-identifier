#!/usr/bin/env python3
"""
Extract audio from video files using FFmpeg.
Outputs a WAV file suitable for audio analysis.
"""

import sys
import json
import subprocess
import os
from pathlib import Path


def find_ffmpeg():
    """Find FFmpeg executable path."""
    # Common locations on macOS
    locations = [
        '/opt/homebrew/bin/ffmpeg',  # Apple Silicon Homebrew
        '/usr/local/bin/ffmpeg',      # Intel Homebrew
        '/usr/bin/ffmpeg',            # System
    ]

    for loc in locations:
        if os.path.isfile(loc):
            return loc

    # Try PATH
    try:
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None


def extract_audio(input_path: str, output_path: str) -> dict:
    """
    Extract audio from a video file.

    Args:
        input_path: Path to input video file
        output_path: Path for output WAV file

    Returns:
        dict with success status and audio path
    """
    ffmpeg_path = find_ffmpeg()

    if not ffmpeg_path:
        return {
            'success': False,
            'error': 'FFmpeg not found. Please install with: brew install ffmpeg'
        }

    if not os.path.isfile(input_path):
        return {
            'success': False,
            'error': f'Input file not found: {input_path}'
        }

    # FFmpeg command to extract audio as 16-bit PCM WAV at 44.1kHz mono
    cmd = [
        ffmpeg_path,
        '-i', input_path,
        '-vn',                    # No video
        '-acodec', 'pcm_s16le',   # 16-bit PCM
        '-ar', '44100',           # 44.1kHz sample rate
        '-ac', '1',               # Mono
        '-y',                     # Overwrite output
        output_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            return {
                'success': False,
                'error': f'FFmpeg error: {result.stderr}'
            }

        if not os.path.isfile(output_path):
            return {
                'success': False,
                'error': 'Output file was not created'
            }

        return {
            'success': True,
            'audioPath': output_path
        }

    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Audio extraction timed out'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def main():
    if len(sys.argv) != 3:
        print(json.dumps({
            'success': False,
            'error': 'Usage: extract_audio.py <input_path> <output_path>'
        }))
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    result = extract_audio(input_path, output_path)
    print(json.dumps(result))

    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
