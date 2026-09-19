"""Not a pytest test — a manual smoke script for the vectorize/centroid/
analyze CLI chain using synthetic data, since P1-P4 need live credentials
and network access this sandbox doesn't have. Run with:

    PV_DATA_DIR=/tmp/pv_smoke .venv/bin/python tests/smoke_e2e.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(os.environ.get("PV_DATA_DIR", "/tmp/pv_smoke"))
shutil.rmtree(DATA_DIR, ignore_errors=True)
DATA_DIR.mkdir(parents=True)

rng = np.random.default_rng(42)
n = 40

# Two synthetic clusters (e.g. "ambient" vs "post-punk") so the silhouette
# sweep and sub-cluster labeling have something real to find.
cluster = rng.integers(0, 2, size=n)
genre_pool = {0: ["ambient", "drone", "downtempo"], 1: ["post-punk", "noise-rock", "shoegaze"]}

tracks = pd.DataFrame(
    {
        "isrc": [f"US{i:08d}" for i in range(n)],
        "title": [f"Track {i}" for i in range(n)],
        "artist_names": [[f"Artist {i % 7}"] for i in range(n)],
        "album": [f"Album {i % 10}" for i in range(n)],
        "release_date": pd.date_range("2015-01-01", periods=n, freq="30D").astype(str),
        "duration_ms": rng.integers(120_000, 300_000, size=n),
        "popularity": rng.integers(0, 100, size=n),
        "explicit": rng.choice([True, False], size=n),
        "added_at": pd.date_range("2023-01-01", periods=n, freq="7D").astype(str),
        "artist_genres": [genre_pool[c] for c in cluster],
    }
)
tracks.to_parquet(DATA_DIR / "tracks.parquet", index=False)

metadata = pd.DataFrame(
    {
        "isrc": tracks["isrc"],
        "mbid": [f"mbid-{i}" for i in range(n)],
        "lastfm_tags": [genre_pool[c] for c in cluster],
    }
)
metadata.to_parquet(DATA_DIR / "features_metadata.parquet", index=False)

base_loudness = np.where(cluster == 0, -20.0, -8.0)
base_dance = np.where(cluster == 0, 0.2, 0.7)
keys = np.where(cluster == 0, "C", "F#")
scales = np.where(cluster == 0, "major", "minor")
bpm = np.where(cluster == 0, 70, 140).astype(float)
embedding_center = np.where(cluster == 0, -1.0, 1.0)

audio_features = pd.DataFrame(
    {
        "isrc": tracks["isrc"],
        "es_danceability": base_dance + rng.normal(0, 0.05, n),
        "es_loudness": base_loudness + rng.normal(0, 1.0, n),
        "es_bpm": bpm + rng.normal(0, 3, n),
        "es_key": keys,
        "es_scale": scales,
        "es_mood_happy": np.clip(base_dance + rng.normal(0, 0.1, n), 0, 1),
        "es_mood_relaxed": np.clip(1 - base_dance + rng.normal(0, 0.1, n), 0, 1),
        "es_embedding": [
            (embedding_center[i] + rng.normal(0, 0.3, 32)).tolist() for i in range(n)
        ],
    }
)
# Simulate partial audio coverage: 15% of tracks missing entirely (no zero-fill!).
missing = rng.choice(n, size=int(n * 0.15), replace=False)
audio_features.loc[missing, audio_features.columns.difference(["isrc"])] = np.nan
audio_features.to_parquet(DATA_DIR / "features_audio.parquet", index=False)

print(f"wrote synthetic checkpoints to {DATA_DIR}")
print(f"{len(missing)}/{n} tracks have no audio features (intentional partial coverage)")
