"""Step 4 (vectorization half) — turn heterogeneous per-track attributes into
one numeric space, block by block, per the four rules in the project plan:

1. Cyclic features (key, tempo) get cyclic encodings, not raw integers.
2. Scale within blocks, not across the whole matrix.
3. Reduce embeddings (PCA/SVD) before combining, not after.
4. Weight blocks deliberately, and record the weights.

Missing data is never zero-filled after scaling (zero == the mean, which
silently drags incomplete tracks toward the center). `Vectorizer.transform`
leaves genuinely missing blocks as NaN; centroid.py consumes that directly
via `nan_euclidean_distances`, and `impute_iterative` is available for the
few consumers (k-means, UMAP) that require a dense matrix.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sklearn.preprocessing import QuantileTransformer, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger(__name__)

MIN_BLOCK_COVERAGE = 0.60


# --- pure encoding helpers (unit-testable without any sklearn state) -------


def circle_of_fifths_position(pitch_class: np.ndarray) -> np.ndarray:
    """Chromatic pitch class (0=C .. 11=B) -> position on the circle of
    fifths. A perfect fifth is 7 semitones, and 7 is its own inverse mod 12,
    so position = (7 * pitch_class) mod 12.
    """
    return (7 * np.asarray(pitch_class)) % 12


def cyclic_key_encode(pitch_class: np.ndarray, is_major: np.ndarray) -> np.ndarray:
    """(n,) pitch classes + (n,) major/minor flags -> (n, 3) [cos, sin, major].

    Using chromatic distance directly implies C (0) and B (11) are maximally
    far apart, when they're a semitone apart. The circle of fifths puts
    harmonically related keys near each other instead.
    """
    pos = circle_of_fifths_position(pitch_class)
    angle = 2 * np.pi * pos / 12
    return np.column_stack([np.cos(angle), np.sin(angle), np.asarray(is_major, dtype=float)])


def fold_tempo_octave(bpm: np.ndarray) -> np.ndarray:
    """log2(bpm) mod 1 — collapses the classic double/half-tempo extractor
    disagreement (85 vs 170 BPM) into the same value, since they differ by
    exactly one octave in log2 space.
    """
    bpm = np.asarray(bpm, dtype=float)
    return (np.log2(bpm) % 1.0).reshape(-1, 1)


# --- block specification -----------------------------------------------------

BlockKind = str  # "acoustic_scalar" | "probability" | "skewed" | "cyclic_key" | "tempo" | "tags" | "embedding"


@dataclass
class BlockSpec:
    name: str
    columns: list[str]
    kind: BlockKind
    weight: float
    reduce_dim: int | None = None  # only used by "tags" and "embedding"


DEFAULT_WEIGHTS = {
    "embedding": 0.40,
    "acoustic_scalar": 0.25,
    "probability": 0.15,
    "tags": 0.15,
    "skewed": 0.05,
    "cyclic_key": 0.05,
    "tempo": 0.05,
}


@dataclass
class FittedBlock:
    spec: BlockSpec
    transformer: object | None
    out_dim: int
    coverage: float
    dropped: bool = False


class Vectorizer:
    """Fits per-block transforms on a dataframe, then produces a single
    (n_tracks, total_dim) matrix with NaN where a block was unavailable for
    a track (or dropped entirely for coverage < MIN_BLOCK_COVERAGE).
    """

    def __init__(self, specs: list[BlockSpec]):
        self.specs = specs
        self.fitted: list[FittedBlock] = []
        self.block_slices: dict[str, slice] = {}
        self.feature_names: list[str] = []

    # -- per-kind fit/transform --------------------------------------------

    @staticmethod
    def _row_mask(df: pd.DataFrame, columns: list[str]) -> np.ndarray:
        return df[columns].notna().any(axis=1).to_numpy()

    def _fit_transform_block(self, df: pd.DataFrame, spec: BlockSpec) -> tuple[np.ndarray, object, float]:
        n = len(df)
        mask = self._row_mask(df, spec.columns)
        coverage = float(mask.mean()) if n else 0.0

        if spec.kind in ("acoustic_scalar", "skewed"):
            raw = df.loc[mask, spec.columns].to_numpy(dtype=float)
            qt = QuantileTransformer(
                output_distribution="normal",
                n_quantiles=min(1000, max(10, mask.sum())),
                subsample=int(1e9),
            )
            scaler = StandardScaler()
            transformed = scaler.fit_transform(qt.fit_transform(raw)) if mask.sum() >= 2 else raw
            out = np.full((n, len(spec.columns)), np.nan)
            out[mask] = transformed
            return out, (qt, scaler), coverage

        if spec.kind == "probability":
            out = df[spec.columns].to_numpy(dtype=float)
            return out, None, coverage

        if spec.kind == "cyclic_key":
            key_col, mode_col = spec.columns
            out = np.full((n, 3), np.nan)
            sub = df.loc[mask]
            out[mask] = cyclic_key_encode(
                sub[key_col].to_numpy(dtype=float), sub[mode_col].to_numpy(dtype=float)
            )
            return out, None, coverage

        if spec.kind == "tempo":
            out = np.full((n, 1), np.nan)
            sub = df.loc[mask, spec.columns[0]].to_numpy(dtype=float)
            out[mask] = fold_tempo_octave(sub)
            return out, None, coverage

        if spec.kind == "tags":
            # parquet round-trips list columns as numpy arrays, not python lists.
            is_seq = lambda x: isinstance(x, (list, tuple, np.ndarray))  # noqa: E731
            tag_lists = df[spec.columns[0]].apply(lambda x: list(x) if is_seq(x) else [])
            has_tags = tag_lists.apply(len).gt(0).to_numpy()
            coverage = float(has_tags.mean()) if n else 0.0
            n_components = spec.reduce_dim or 15
            if has_tags.sum() < 2:
                return np.full((n, n_components), np.nan), None, coverage
            tfidf = TfidfVectorizer(analyzer=lambda tags: tags)
            X_tfidf = tfidf.fit_transform(tag_lists[has_tags])
            n_components = min(n_components, X_tfidf.shape[1] - 1, X_tfidf.shape[0] - 1)
            n_components = max(n_components, 1)
            svd = TruncatedSVD(n_components=n_components)
            reduced = svd.fit_transform(X_tfidf)
            scaler = StandardScaler()
            reduced = scaler.fit_transform(reduced)
            out = np.full((n, n_components), np.nan)
            out[has_tags] = reduced
            return out, (tfidf, svd, scaler), coverage

        if spec.kind == "embedding":
            vectors = df[spec.columns[0]]
            has_vec = vectors.apply(lambda x: isinstance(x, (list, tuple, np.ndarray)) and len(x) > 0)
            has_vec = has_vec.to_numpy()
            coverage = float(has_vec.mean()) if n else 0.0
            n_components = spec.reduce_dim or 30
            if has_vec.sum() < 2:
                return np.full((n, n_components), np.nan), None, coverage
            raw = np.stack(vectors[has_vec].to_numpy())
            norms = np.linalg.norm(raw, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            l2_normalized = raw / norms  # reduce embeddings while alone (rule 3), L2-normalize first
            n_components = min(n_components, l2_normalized.shape[1] - 1, l2_normalized.shape[0] - 1)
            n_components = max(n_components, 1)
            pca = PCA(n_components=n_components)
            reduced = pca.fit_transform(l2_normalized)
            scaler = StandardScaler()
            reduced = scaler.fit_transform(reduced)
            out = np.full((n, n_components), np.nan)
            out[has_vec] = reduced
            return out, (pca, scaler), coverage

        raise ValueError(f"unknown block kind: {spec.kind}")

    def fit_transform(self, df: pd.DataFrame, weights: dict[str, float] | None = None) -> np.ndarray:
        weights = weights or DEFAULT_WEIGHTS
        blocks_out = []
        col = 0
        self.block_slices = {}
        self.feature_names = []
        self.fitted = []

        for spec in self.specs:
            block_matrix, transformer, coverage = self._fit_transform_block(df, spec)
            dropped = coverage < MIN_BLOCK_COVERAGE
            if dropped:
                log.warning(
                    "block %r coverage %.1f%% is below %.0f%% — dropping it "
                    "from the vector space (see project plan pitfalls table)",
                    spec.name,
                    coverage * 100,
                    MIN_BLOCK_COVERAGE * 100,
                )
                self.fitted.append(FittedBlock(spec, transformer, block_matrix.shape[1], coverage, dropped=True))
                continue

            weight = weights.get(spec.kind, weights.get(spec.name, 1.0))
            dim = block_matrix.shape[1]
            scale_factor = np.sqrt(weight / dim) if dim else 0.0
            weighted = block_matrix * scale_factor

            self.fitted.append(FittedBlock(spec, transformer, dim, coverage, dropped=False))
            self.block_slices[spec.name] = slice(col, col + dim)
            self.feature_names.extend(f"{spec.name}_{i}" for i in range(dim))
            col += dim
            blocks_out.append(weighted)

        if not blocks_out:
            raise ValueError("every block was dropped for low coverage — nothing to vectorize")

        return np.hstack(blocks_out)

    def weights_manifest(self) -> dict:
        return {
            fb.spec.name: {
                "kind": fb.spec.kind,
                "weight": fb.spec.weight,
                "out_dim": fb.out_dim,
                "coverage": fb.coverage,
                "dropped": fb.dropped,
            }
            for fb in self.fitted
        }


def impute_iterative(X: np.ndarray, random_state: int = 0) -> np.ndarray:
    """Dense, NaN-free matrix for consumers that require one (k-means, UMAP).
    Prefer `nan_euclidean_distances` directly wherever a consumer supports it —
    it doesn't invent values, it just skips missing dimensions pairwise.
    """
    if not np.isnan(X).any():
        return X
    imputer = IterativeImputer(random_state=random_state, max_iter=25)
    return imputer.fit_transform(X)


def default_specs_from_columns(columns: list[str]) -> list[BlockSpec]:
    """Best-effort block layout given whatever columns actually made it
    through P1-P4 for this playlist. Callers with a fixed schema should
    build `BlockSpec` lists explicitly instead — this exists so the CLI has
    a sane default on a playlist with partial coverage.
    """
    specs: list[BlockSpec] = []

    scalar_candidates = [
        c
        for c in ("es_danceability", "es_loudness", "ab_danceability", "ab_loudness", "lr_rms_mean")
        if c in columns
    ]
    if scalar_candidates:
        specs.append(BlockSpec("acoustic_scalars", scalar_candidates, "acoustic_scalar", DEFAULT_WEIGHTS["acoustic_scalar"]))

    prob_candidates = [c for c in columns if c.startswith("es_mood_") or c.startswith("ab_mood_")]
    if prob_candidates:
        specs.append(BlockSpec("mood", prob_candidates, "probability", DEFAULT_WEIGHTS["probability"]))

    if "es_bpm" in columns or "ab_bpm" in columns or "lr_tempo_bpm" in columns:
        bpm_col = next(c for c in ("es_bpm", "ab_bpm", "lr_tempo_bpm") if c in columns)
        specs.append(BlockSpec("tempo", [bpm_col], "tempo", DEFAULT_WEIGHTS["tempo"]))

    skewed_candidates = [c for c in ("duration_ms", "popularity", "release_year") if c in columns]
    if skewed_candidates:
        specs.append(BlockSpec("metadata", skewed_candidates, "skewed", DEFAULT_WEIGHTS["skewed"]))

    if "artist_genres" in columns:
        specs.append(BlockSpec("genre_tags", ["artist_genres"], "tags", DEFAULT_WEIGHTS["tags"], reduce_dim=15))
    elif "lastfm_tags" in columns:
        specs.append(BlockSpec("genre_tags", ["lastfm_tags"], "tags", DEFAULT_WEIGHTS["tags"], reduce_dim=15))

    if "es_embedding" in columns:
        specs.append(BlockSpec("embedding", ["es_embedding"], "embedding", DEFAULT_WEIGHTS["embedding"], reduce_dim=30))

    return specs


def save_manifest(vectorizer: Vectorizer, path: Path) -> None:
    path.write_text(json.dumps(vectorizer.weights_manifest(), indent=2))
