"""Essentia feature extraction — the closest free substitute for Spotify's
retired `audio_features`. Two independent things happen here:

1. `essentia.standard.MusicExtractor` computes ~40 low-level/rhythm/tonal
   descriptors natively — no model download required. This always works once
   `essentia-tensorflow` is installed.

2. Discogs-EffNet embeddings + classifier heads (mood, danceability, genre)
   require separately downloaded `.pb` model files from
   https://essentia.upf.edu/models.html. THE MTG MODELS ARE LICENSED
   CC BY-NC-SA 4.0 — non-commercial only. This module only touches them if
   ESSENTIA_MODELS_DIR is set and populated; otherwise it silently skips
   step 2 and you still get the MusicExtractor descriptors.

Essentia is deliberately lazy-imported: the rest of this package works
without it installed, since `essentia-tensorflow` is picky about Python
versions and heavy to build (see README).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_licensing_note_shown = False


def _warn_license_once() -> None:
    global _licensing_note_shown
    if not _licensing_note_shown:
        log.warning(
            "Loading MTG pretrained models: these are CC BY-NC-SA 4.0 "
            "(non-commercial only). Fine for a personal playlist project; "
            "swap to CLAP/MERT (Apache-2.0) before shipping anything that "
            "uses this output commercially."
        )
        _licensing_note_shown = True


def _require_essentia():
    try:
        import essentia  # noqa: F401
        import essentia.standard as es
    except ImportError as exc:
        raise SystemExit(
            "essentia is not installed. Install it with "
            "`pip install '.[essentia]'` inside the venv (see README for the "
            "Python-version caveats), or use the librosa fallback instead."
        ) from exc
    return es


_LOWLEVEL_FIELDS = {
    "rhythm.bpm": "es_bpm",
    "rhythm.danceability": "es_danceability",
    "tonal.key_key": "es_key",
    "tonal.key_scale": "es_scale",
    "lowlevel.average_loudness": "es_loudness",
    "lowlevel.dynamic_complexity": "es_dynamic_complexity",
    "lowlevel.spectral_energy.mean": "es_spectral_energy_mean",
    "lowlevel.spectral_centroid.mean": "es_spectral_centroid_mean",
}


def extract_music_extractor(audio_path: str) -> dict:
    """Run MusicExtractor — no model downloads needed."""
    es = _require_essentia()
    features, _ = es.MusicExtractor()(audio_path)

    out: dict = {}
    for descriptor_key, out_key in _LOWLEVEL_FIELDS.items():
        try:
            out[out_key] = features[descriptor_key]
        except KeyError:
            out[out_key] = None
    return out


@dataclass(frozen=True)
class ClassifierHead:
    """One Discogs-EffNet classifier head.

    `positive_index` is the output index whose probability you want to keep
    as this feature's value. Essentia's model zoo pages
    (https://essentia.upf.edu/models.html) list each head's class order in
    its accompanying `.json` metadata — check it there rather than assuming;
    getting this wrong silently flips a mood score.
    """

    pb_filename: str
    output_feature_name: str
    positive_index: int = 1


DEFAULT_CLASSIFIER_HEADS = [
    ClassifierHead("mood_happy-discogs-effnet-1.pb", "es_mood_happy"),
    ClassifierHead("mood_sad-discogs-effnet-1.pb", "es_mood_sad"),
    ClassifierHead("mood_aggressive-discogs-effnet-1.pb", "es_mood_aggressive"),
    ClassifierHead("mood_relaxed-discogs-effnet-1.pb", "es_mood_relaxed"),
    ClassifierHead("mood_party-discogs-effnet-1.pb", "es_mood_party"),
    ClassifierHead("danceability-discogs-effnet-1.pb", "es_danceability_clf"),
]

_EMBEDDING_MODEL_FILENAME = "discogs-effnet-bs64-1.pb"


def extract_embedding_and_heads(
    audio_path: str,
    models_dir: Path,
    heads: list[ClassifierHead] | None = None,
) -> tuple[np.ndarray | None, dict]:
    """Discogs-EffNet embedding (1280-d) plus whichever classifier heads are
    present on disk under `models_dir`. Missing model files are skipped, not
    fatal — this lets you start with just the embedding model and add
    classifier heads incrementally.
    """
    es = _require_essentia()
    heads = heads if heads is not None else DEFAULT_CLASSIFIER_HEADS

    embedding_path = models_dir / _EMBEDDING_MODEL_FILENAME
    if not embedding_path.exists():
        log.warning("embedding model not found at %s; skipping embedding+heads", embedding_path)
        return None, {}

    _warn_license_once()
    audio = es.MonoLoader(filename=audio_path, sampleRate=16000)()

    embedding_model = es.TensorflowPredictEffnetDiscogs(
        graphFilename=str(embedding_path), output="PartitionedCall:1"
    )
    embeddings = embedding_model(audio)  # (n_patches, 1280)
    embedding = np.mean(embeddings, axis=0)

    scalar_outputs: dict = {}
    for head in heads:
        head_path = models_dir / head.pb_filename
        if not head_path.exists():
            continue
        predictor = es.TensorflowPredict2D(graphFilename=str(head_path))
        predictions = predictor(embeddings)  # (n_patches, n_classes)
        scalar_outputs[head.output_feature_name] = float(
            np.mean(predictions[:, head.positive_index])
        )

    return embedding, scalar_outputs


def extract_all(audio_path: str, models_dir: Path | None) -> dict:
    """Convenience entry point used by the CLI: MusicExtractor descriptors
    plus embedding+heads if `models_dir` is configured and populated.
    """
    out = extract_music_extractor(audio_path)
    if models_dir is not None:
        embedding, heads_out = extract_embedding_and_heads(audio_path, models_dir)
        out.update(heads_out)
        if embedding is not None:
            out["es_embedding"] = embedding.tolist()
    return out
