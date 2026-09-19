"""Step 2 (metadata half) — join tracks.parquet against free metadata sources.

Waterfall order: MusicBrainz (ISRC -> MBID) is required for everything else,
then AcousticBrainz (offline, free, no rate limit) is tried first since it
needs no network call per track, then Last.fm and Discogs fill in tags.

Writes features_metadata.parquet, one row per ISRC, plus a coverage report so
you can decide at the P2/P3 boundary whether audio fetching (P3-P4) is even
worth doing for this playlist.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
from tqdm import tqdm

from . import acousticbrainz, discogs, lastfm, mb
from .cache import DiskCache, RateLimiter
from .config import Config

log = logging.getLogger(__name__)


def run(cfg: Config, use_discogs: bool = False) -> pd.DataFrame:
    tracks = pd.read_parquet(cfg.tracks_path)
    tracks = tracks[tracks["isrc"].notna()].reset_index(drop=True)

    mb_cache = DiskCache(cfg.cache_dir, "musicbrainz")
    mb_limiter = RateLimiter(1.05)  # MusicBrainz: 1 req/sec, pad slightly

    lastfm_cache = DiskCache(cfg.cache_dir, "lastfm")
    lastfm_limiter = RateLimiter(0.25)  # ~5 req/sec allowed for free-tier keys

    discogs_cache = DiskCache(cfg.cache_dir, "discogs")
    discogs_limiter = RateLimiter(1.05)  # 60 req/min

    ab_index = None
    if cfg.acousticbrainz_dump_dir is not None:
        ab_index = acousticbrainz.build_index(cfg.acousticbrainz_dump_dir)

    rows = []
    for _, track in tqdm(tracks.iterrows(), total=len(tracks), desc="enrich"):
        artist = track["artist_names"][0] if len(track["artist_names"]) else ""
        row: dict = {"isrc": track["isrc"]}

        mbid = mb.isrc_to_mbid(cfg, track["isrc"], mb_cache, mb_limiter)
        row["mbid"] = mbid

        if mbid and ab_index is not None:
            ab_features = acousticbrainz.lookup(ab_index, mbid)
            if ab_features:
                row.update(ab_features)

        tags = lastfm.top_tags(cfg, artist, track["title"], lastfm_cache, lastfm_limiter)
        row["lastfm_tags"] = [t for t, _ in tags]
        row["lastfm_tag_weights"] = [w for _, w in tags]

        if use_discogs:
            gs = discogs.genres_and_styles(cfg, artist, track["title"], discogs_cache, discogs_limiter)
            row["discogs_genres"] = gs["genres"]
            row["discogs_styles"] = gs["styles"]

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_parquet(cfg.features_metadata_path, index=False)

    report = {
        "n_tracks": len(tracks),
        "mbid_coverage": float(df["mbid"].notna().mean()),
        "acousticbrainz_lowlevel_coverage": float(df["ab_bpm"].notna().mean()) if "ab_bpm" in df else 0.0,
        "acousticbrainz_highlevel_coverage": (
            float(df["ab_danceability"].notna().mean()) if "ab_danceability" in df else 0.0
        ),
        "lastfm_tag_coverage": float(df["lastfm_tags"].apply(len).gt(0).mean()),
    }
    (cfg.data_dir / "coverage_report.json").write_text(json.dumps(report, indent=2))
    log.info("coverage report: %s", report)
    if report["acousticbrainz_highlevel_coverage"] > 0.70:
        log.info(
            "AcousticBrainz high-level coverage is >70%% — per the project plan, "
            "P3/P4 (audio fetch + Essentia) may not be worth doing for v1."
        )

    return df
