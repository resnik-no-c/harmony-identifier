"""DSP feature fallback using librosa — no model downloads, no licensing
questions, works the moment `pip install librosa` finishes. Weaker than the
Essentia route (Step 3 in the project plan) but always available, so it's a
reasonable baseline or a stand-in while you decide whether Essentia is worth
installing for this playlist.
"""

from __future__ import annotations

import logging

import librosa
import numpy as np

log = logging.getLogger(__name__)


def extract(audio_path: str, offset_s: float = 0.0, duration_s: float | None = 30.0) -> dict:
    y, sr = librosa.load(audio_path, sr=None, mono=True, offset=offset_s, duration=duration_s)
    if y.size == 0:
        raise ValueError(f"empty audio: {audio_path}")

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)
    tempo, _ = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

    features: dict = {
        "lr_tempo_bpm": float(np.atleast_1d(tempo)[0]),
        "lr_spectral_centroid_mean": float(centroid.mean()),
        "lr_spectral_rolloff_mean": float(rolloff.mean()),
        "lr_onset_strength_mean": float(onset_env.mean()),
        "lr_rms_mean": float(rms.mean()),
    }
    for i in range(mfcc.shape[0]):
        features[f"lr_mfcc_{i}_mean"] = float(mfcc[i].mean())
        features[f"lr_mfcc_{i}_std"] = float(mfcc[i].std())
    for i in range(contrast.shape[0]):
        features[f"lr_contrast_{i}_mean"] = float(contrast[i].mean())
    for i in range(chroma.shape[0]):
        features[f"lr_chroma_{i}_mean"] = float(chroma[i].mean())

    return features
