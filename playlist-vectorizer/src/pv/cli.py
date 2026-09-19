"""Command-line entry point. Each subcommand is one phase from the project
plan (P1-P6) and reads/writes the parquet checkpoints in PV_DATA_DIR, so any
phase can be re-run on its own without redoing the ones before it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
import numpy as np
import pandas as pd

from .config import load_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pv.cli")

NOTE_TO_PITCH_CLASS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


@click.group()
def main():
    """Spotify playlist vectorization & centroid pipeline."""


@main.command("export")
@click.option("--playlist-id", required=True, help="Spotify playlist ID or URI.")
def export_cmd(playlist_id: str):
    """P1 — export a playlist to tracks.parquet/csv."""
    from . import export

    cfg = load_config()
    df = export.export_playlist(cfg, playlist_id)
    export.save(df, cfg)


@main.command("enrich")
@click.option("--use-discogs", is_flag=True, default=False)
def enrich_cmd(use_discogs: bool):
    """P2 — join free metadata sources (MusicBrainz/AcousticBrainz/Last.fm)."""
    from . import enrich

    cfg = load_config()
    enrich.run(cfg, use_discogs=use_discogs)


@main.command("fetch-audio")
@click.option("--library-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Local music library to match by ISRC tag before trying Deezer.")
def fetch_audio_cmd(library_dir: str | None):
    """P3 — resolve ~30s of audio per track (local files, then Deezer preview)."""
    from . import audio_fetch

    cfg = load_config()
    audio_fetch.run(cfg, Path(library_dir) if library_dir else None)


@main.command("extract-features")
@click.option("--engine", type=click.Choice(["librosa", "essentia"]), default="librosa")
def extract_features_cmd(engine: str):
    """P4 — run feature extraction over whatever audio P3 resolved."""
    from . import features

    cfg = load_config()
    features.run(cfg, engine=engine)


def _load_merged(cfg) -> pd.DataFrame:
    tracks = pd.read_parquet(cfg.tracks_path)
    df = tracks
    if cfg.features_metadata_path.exists():
        meta = pd.read_parquet(cfg.features_metadata_path)
        df = df.merge(meta, on="isrc", how="left")
    if cfg.features_audio_path.exists():
        audio = pd.read_parquet(cfg.features_audio_path)
        df = df.merge(audio, on="isrc", how="left")

    if "release_date" in df.columns:
        df["release_year"] = pd.to_datetime(df["release_date"], errors="coerce").dt.year

    # Normalize whichever key/scale columns are present (essentia uses note
    # names; acousticbrainz mirrors that) into an integer pitch class + major flag.
    for prefix in ("es", "ab"):
        key_col, scale_col = f"{prefix}_key", f"{prefix}_scale"
        if key_col in df.columns:
            df[f"{key_col}_pc"] = df[key_col].map(NOTE_TO_PITCH_CLASS)
            df[f"{prefix}_is_major"] = df[scale_col].map({"major": 1, "minor": 0}) if scale_col in df.columns else np.nan

    return df


@main.command("vectorize")
def vectorize_cmd():
    """P5 (encode) — merge all sources and encode into block-weighted vectors."""
    from . import vectorize as vec

    cfg = load_config()
    df = _load_merged(cfg)

    specs = vec.default_specs_from_columns(list(df.columns))
    # Prefer a proper cyclic key block if a normalized key/scale pair exists.
    for prefix in ("es", "ab"):
        pc_col, major_col = f"{prefix}_key_pc", f"{prefix}_is_major"
        if pc_col in df.columns and major_col in df.columns:
            specs.append(vec.BlockSpec("key", [pc_col, major_col], "cyclic_key", vec.DEFAULT_WEIGHTS["cyclic_key"]))
            break

    if not specs:
        raise SystemExit(
            "No usable feature columns found. Run `pv enrich` and/or "
            "`pv extract-features` before vectorizing."
        )

    vectorizer = vec.Vectorizer(specs)
    X = vectorizer.fit_transform(df)

    np.save(cfg.data_dir / "vectors.npy", X)
    df[["isrc"]].to_parquet(cfg.vectors_path, index=False)
    vec.save_manifest(vectorizer, cfg.data_dir / "block_weights.json")

    log.info("vectorized %d tracks into %d dimensions across %d blocks", *X.shape, len(vectorizer.block_slices))
    log.info("block manifest written to %s", cfg.data_dir / "block_weights.json")


@main.command("centroid")
def centroid_cmd():
    """P5 (reduce) — four centroid variants, dispersion, and the silhouette
    unimodality check."""
    from . import centroid as cen
    from . import vectorize as vec

    cfg = load_config()
    X = np.load(cfg.data_dir / "vectors.npy")
    manifest = json.loads((cfg.data_dir / "block_weights.json").read_text())

    block_slices = {}
    col = 0
    for name, info in manifest.items():
        if info["dropped"]:
            continue
        block_slices[name] = slice(col, col + info["out_dim"])
        col += info["out_dim"]

    X_dense = vec.impute_iterative(X)
    report = cen.compute_all(X, block_slices, X_dense_for_silhouette=X_dense)

    out = {
        "euclidean_mean": report.euclidean_mean.tolist(),
        "spherical_mean": report.spherical_mean.tolist() if report.spherical_mean is not None else None,
        "geometric_median": report.geometric_median.tolist() if report.geometric_median is not None else None,
        "medoid_index": report.medoid_index,
        "mean_distance_to_centroid": report.mean_distance_to_centroid,
        "per_block_distance": report.per_block_distance,
        "silhouette": [{"k": r.k, "score": r.score} for r in report.silhouette],
        "is_unimodal": report.is_unimodal,
    }
    cfg.centroids_path.write_text(json.dumps(out, indent=2))

    ids = pd.read_parquet(cfg.vectors_path)
    log.info("medoid track ISRC: %s", ids.iloc[report.medoid_index]["isrc"])
    log.info("mean distance to centroid (coherence): %.4f", report.mean_distance_to_centroid)
    if not report.is_unimodal:
        log.warning(
            "Silhouette sweep suggests this playlist is not one cluster "
            "(%s). Consider reporting per-cluster centroids instead of one.",
            out["silhouette"],
        )
    log.info("wrote %s", cfg.centroids_path)


@main.command("analyze")
@click.option("--viz/--no-viz", default=False, help="Also write a UMAP scatter plot + radar chart (needs `.[viz]`).")
def analyze_cmd(viz: bool):
    """P6 — most/least representative track, and optional plots."""
    from . import analysis, vectorize as vec

    cfg = load_config()
    df = _load_merged(cfg)
    X = np.load(cfg.data_dir / "vectors.npy")
    centroid_report = json.loads(cfg.centroids_path.read_text())
    centroid = np.array(centroid_report["euclidean_mean"])

    most, least = analysis.most_and_least_representative(df, X, centroid, ["isrc", "title", "artist_names"])
    log.info("most representative: %s — %s", most["title"], most["artist_names"])
    log.info("least representative: %s — %s", least["title"], least["artist_names"])

    if viz:
        X_dense = vec.impute_iterative(X)
        reducer, embedding = analysis.fit_umap(X_dense)
        centroid_2d = analysis.project_point(reducer, centroid)

        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 8))
        ax.scatter(embedding[:, 0], embedding[:, 1], alpha=0.6, label="tracks")
        ax.scatter(*centroid_2d, color="red", marker="*", s=300, label="centroid (projected)")
        ax.legend()
        ax.set_title("Playlist UMAP projection")
        fig.tight_layout()
        fig.savefig(cfg.data_dir / "umap.png", dpi=150)
        log.info("wrote %s", cfg.data_dir / "umap.png")


if __name__ == "__main__":
    main()
