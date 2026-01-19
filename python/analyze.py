#!/usr/bin/env python3
"""
Audio analysis script for chord and key detection.
Uses madmom for chord recognition and librosa for key detection.
"""

import sys
import json
import os
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

import numpy as np
import librosa


def detect_key(y: np.ndarray, sr: int) -> tuple:
    """
    Detect the musical key using chroma features and the Krumhansl-Schmuckler algorithm.

    Args:
        y: Audio time series
        sr: Sample rate

    Returns:
        tuple of (key_name, confidence)
    """
    # Compute chroma features
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Average chroma over time
    chroma_avg = np.mean(chroma, axis=1)

    # Krumhansl-Kessler key profiles
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    # Pitch class names
    pitch_classes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    best_key = None
    best_corr = -1

    # Test all major and minor keys
    for i in range(12):
        # Rotate chroma to align with key
        rotated_chroma = np.roll(chroma_avg, -i)

        # Correlate with major profile
        major_corr = np.corrcoef(rotated_chroma, major_profile)[0, 1]
        if major_corr > best_corr:
            best_corr = major_corr
            best_key = f"{pitch_classes[i]} major"

        # Correlate with minor profile
        minor_corr = np.corrcoef(rotated_chroma, minor_profile)[0, 1]
        if minor_corr > best_corr:
            best_corr = minor_corr
            best_key = f"{pitch_classes[i]} minor"

    # Convert correlation to confidence (0-1 range)
    confidence = max(0, min(1, (best_corr + 1) / 2))

    return best_key, confidence


def detect_chords_madmom(y: np.ndarray, sr: int, segment_start: float, beats_per_measure: int = 4, beats_to_group: int = 4) -> list:
    """
    Detect chords using madmom's CNN-based chord recognition.

    Args:
        y: Audio time series
        sr: Sample rate
        segment_start: Start time of segment (for time offset)
        beats_per_measure: Number of beats per measure (e.g., 4 for 4/4, 3 for 3/4, 6 for 6/8)
        beats_to_group: Number of beats to group for each chord (controls granularity)

    Returns:
        List of chord dictionaries with start time and chord name
    """
    try:
        from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor

        # Create temporary file for madmom (it needs a file path)
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
            sf.write(tmp_path, y, sr)

        try:
            # Initialize processors
            feat_proc = CNNChordFeatureProcessor()
            chord_proc = CRFChordRecognitionProcessor()

            # Extract features and decode chords
            features = feat_proc(tmp_path)
            chords = chord_proc(features)

            # Process results
            result = []
            prev_chord = None

            for start, end, chord in chords:
                # Skip 'N' (no chord) labels
                if chord == 'N':
                    continue

                # Only add if different from previous
                if chord != prev_chord:
                    result.append({
                        'start': round(segment_start + start, 2),
                        'end': round(segment_start + end, 2),
                        'chord': chord
                    })
                    prev_chord = chord

            return result

        finally:
            os.unlink(tmp_path)

    except ImportError:
        # Fallback to librosa-based chord detection
        return detect_chords_librosa(y, sr, segment_start, beats_per_measure, beats_to_group)
    except Exception as e:
        # Fallback on any error
        return detect_chords_librosa(y, sr, segment_start, beats_per_measure, beats_to_group)


def detect_chords_librosa(y: np.ndarray, sr: int, segment_start: float, beats_per_measure: int = 4, beats_to_group: int = 4) -> list:
    """
    Chord detection using librosa's chroma features with beat-aware grouping.
    Returns one chord per group of beats for adjustable granularity.

    Args:
        y: Audio time series
        sr: Sample rate
        segment_start: Start time of segment
        beats_per_measure: Number of beats per measure (e.g., 4 for 4/4, 3 for 3/4, 6 for 6/8)
        beats_to_group: Number of beats to group for each chord (controls granularity)

    Returns:
        List of chord dictionaries (one per beat group)
    """
    # Chord templates (major and minor triads)
    chord_templates = {
        'C': [1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0],
        'C#': [0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
        'D': [0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0],
        'D#': [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0],
        'E': [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1],
        'F': [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
        'F#': [0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
        'G': [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1],
        'G#': [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0],
        'A': [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
        'A#': [0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 0],
        'B': [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1],
        'Cm': [1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
        'C#m': [0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        'Dm': [0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0],
        'D#m': [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0],
        'Em': [0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
        'Fm': [1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0],
        'F#m': [0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
        'Gm': [0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0],
        'G#m': [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1],
        'Am': [1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
        'A#m': [0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0],
        'Bm': [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    }

    # Convert templates to numpy arrays
    templates = {name: np.array(t) for name, t in chord_templates.items()}

    # Detect tempo automatically
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(tempo)

    # Map user's time signature to expected librosa pulse level
    # Compound meters (6/8, 9/8, 12/8) are felt in larger groupings
    if beats_per_measure == 6:  # 6/8 compound meter - felt in 2
        librosa_pulses_per_measure = 2
    elif beats_per_measure == 9:  # 9/8 - felt in 3
        librosa_pulses_per_measure = 3
    elif beats_per_measure == 12:  # 12/8 - felt in 4
        librosa_pulses_per_measure = 4
    else:  # Simple meters (2/4, 3/4, 4/4) - pulse equals beats
        librosa_pulses_per_measure = beats_per_measure

    # Calculate measure duration from detected tempo
    measure_duration = (60.0 / tempo) * librosa_pulses_per_measure

    # Calculate interval based on granularity setting
    # beats_to_group / beats_per_measure gives the fraction of a measure
    interval_duration = measure_duration * (beats_to_group / beats_per_measure)

    # Create fixed-interval boundaries (more reliable than grouping detected beats)
    duration = len(y) / sr
    group_starts = list(np.arange(0, duration, interval_duration))
    group_ends = group_starts[1:] + [duration]

    # Compute chroma features at higher resolution for accurate analysis
    hop_length = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)
    frame_times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=hop_length)

    chords = []

    for group_start, group_end in zip(group_starts, group_ends):
        # Find frames within this group
        mask = (frame_times >= group_start) & (frame_times < group_end)
        if not np.any(mask):
            continue

        # Average chroma over the group
        group_chroma = np.mean(chroma[:, mask], axis=1)
        group_chroma_norm = group_chroma / (np.linalg.norm(group_chroma) + 1e-10)

        # Find best matching chord
        best_chord = None
        best_score = -1

        for name, template in templates.items():
            template_norm = template / (np.linalg.norm(template) + 1e-10)
            score = np.dot(group_chroma_norm, template_norm)
            if score > best_score:
                best_score = score
                best_chord = name

        # Add chord for each interval (no merging - keeps timing consistent)
        if best_score > 0.6:
            chords.append({
                'start': round(segment_start + group_start, 2),
                'end': round(segment_start + group_end, 2),
                'chord': best_chord
            })

    return chords


def analyze_segment(audio_path: str, start_time: float, end_time: float, beats_per_measure: int = 4, beats_to_group: int = 4) -> dict:
    """
    Analyze an audio segment for chords and key.

    Args:
        audio_path: Path to audio file
        start_time: Start time in seconds
        end_time: End time in seconds
        beats_per_measure: Number of beats per measure (e.g., 4 for 4/4, 3 for 3/4, 6 for 6/8)
        beats_to_group: Number of beats to group for each chord (controls granularity)

    Returns:
        dict with key, confidence, and chords
    """
    if not os.path.isfile(audio_path):
        return {
            'error': f'Audio file not found: {audio_path}'
        }

    try:
        # Load audio segment
        y, sr = librosa.load(
            audio_path,
            sr=44100,
            offset=start_time,
            duration=end_time - start_time
        )

        if len(y) == 0:
            return {
                'error': 'Audio segment is empty'
            }

        # Detect key
        key, confidence = detect_key(y, sr)

        # Detect chords
        chords = detect_chords_madmom(y, sr, start_time, beats_per_measure, beats_to_group)

        return {
            'key': key,
            'confidence': round(confidence, 3),
            'chords': chords
        }

    except Exception as e:
        return {
            'error': str(e)
        }


def main():
    if len(sys.argv) < 4:
        print(json.dumps({
            'error': 'Usage: analyze.py <audio_path> <start_time> <end_time> [beats_per_measure] [beats_to_group]'
        }))
        sys.exit(1)

    audio_path = sys.argv[1]
    start_time = float(sys.argv[2])
    end_time = float(sys.argv[3])
    beats_per_measure = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    beats_to_group = int(sys.argv[5]) if len(sys.argv) > 5 else beats_per_measure

    result = analyze_segment(audio_path, start_time, end_time, beats_per_measure, beats_to_group)
    print(json.dumps(result))

    sys.exit(0 if 'error' not in result else 1)


if __name__ == '__main__':
    main()
