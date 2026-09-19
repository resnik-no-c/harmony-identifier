"""Step 3 — get ~30s of representative audio per track, cached and resumable.

Routes, in the order the plan recommends trying them:

1. Your own local files, matched by ISRC tag (or artist+title fallback).
2. Deezer's public `track/isrc:{ISRC}` endpoint, which resolves an ISRC
   without auth and returns a 30s preview MP3 URL. This is the standard
   post-deprecation MIR workaround — but it's an unauthenticated public
   endpoint on someone else's service, so *verify it still behaves this way*
   before leaning on it, and mind Deezer's API terms for your use case.
4. (Streaming-site extraction is deliberately not implemented here — it's
   widely done in academic MIR but against most platforms' terms of service.)

Coverage will not hit 100%. Don't drop the misses — that biases the centroid
toward popular, well-distributed releases. `manifest.parquet` records a
status per ISRC (`ok` / `no_match` / `error`) so downstream stages can carry
an explicit coverage column instead of silently shrinking the dataset.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests
from mutagen import File as MutagenFile
from tqdm import tqdm

from .cache import DiskCache, RateLimiter
from .config import Config

log = logging.getLogger(__name__)

_DEEZER_URL = "https://api.deezer.com/2.0/track/isrc:{isrc}"
_AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac"}


def _read_isrc_tag(path: Path) -> str | None:
    try:
        tags = MutagenFile(path, easy=True)
    except Exception:  # noqa: BLE001
        return None
    if not tags:
        return None
    for key in ("isrc",):
        val = tags.get(key)
        if val:
            return str(val[0]).upper().replace("-", "")
    return None


def index_local_library(library_dir: Path) -> dict[str, Path]:
    """Scan a local music library and return {isrc: filepath} for tagged files."""
    index: dict[str, Path] = {}
    paths = [p for p in library_dir.rglob("*") if p.suffix.lower() in _AUDIO_EXTS]
    for path in tqdm(paths, desc="indexing local library"):
        isrc = _read_isrc_tag(path)
        if isrc:
            index[isrc] = path
    log.info("indexed %d ISRC-tagged local files", len(index))
    return index


def _deezer_preview_url(isrc: str, cache: DiskCache, limiter: RateLimiter) -> str | None:
    cached = cache.get(isrc)
    if cached is not None:
        return cached.get("preview_url")

    limiter.wait()
    try:
        resp = requests.get(_DEEZER_URL.format(isrc=isrc), timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning("Deezer lookup failed for %s: %s", isrc, exc)
        return None

    if data.get("error"):
        cache.set(isrc, {"preview_url": None})
        return None

    preview = data.get("preview") or None
    cache.set(isrc, {"preview_url": preview})
    return preview


def _download(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("download failed for %s: %s", url, exc)
        return False
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)
    return True


def run(cfg: Config, local_library_dir: Path | None = None) -> pd.DataFrame:
    tracks = pd.read_parquet(cfg.tracks_path)
    tracks = tracks[tracks["isrc"].notna()].reset_index(drop=True)
    cfg.audio_dir.mkdir(parents=True, exist_ok=True)

    local_index = index_local_library(local_library_dir) if local_library_dir else {}

    deezer_cache = DiskCache(cfg.cache_dir, "deezer")
    deezer_limiter = RateLimiter(0.2)  # be polite to an unauthenticated public endpoint

    existing = (
        pd.read_parquet(cfg.manifest_path) if cfg.manifest_path.exists() else pd.DataFrame(columns=["isrc"])
    )
    done_isrcs = set(existing.loc[existing["status"] == "ok", "isrc"]) if not existing.empty else set()

    rows = []
    for _, track in tqdm(tracks.iterrows(), total=len(tracks), desc="audio fetch"):
        isrc = track["isrc"]
        if isrc in done_isrcs:
            continue

        dest = cfg.audio_dir / f"{isrc}.mp3"

        if isrc in local_index:
            rows.append({"isrc": isrc, "path": str(local_index[isrc]), "source": "local", "status": "ok"})
            continue

        if dest.exists():
            rows.append({"isrc": isrc, "path": str(dest), "source": "cached", "status": "ok"})
            continue

        preview_url = _deezer_preview_url(isrc, deezer_cache, deezer_limiter)
        if preview_url and _download(preview_url, dest):
            rows.append({"isrc": isrc, "path": str(dest), "source": "deezer", "status": "ok"})
        elif preview_url is None:
            rows.append({"isrc": isrc, "path": None, "source": None, "status": "no_match"})
        else:
            rows.append({"isrc": isrc, "path": None, "source": "deezer", "status": "error"})

    new_manifest = pd.DataFrame(rows)
    manifest = pd.concat([existing, new_manifest], ignore_index=True).drop_duplicates(
        subset="isrc", keep="last"
    )
    manifest.to_parquet(cfg.manifest_path, index=False)

    coverage = (manifest["status"] == "ok").mean() if len(manifest) else 0.0
    log.info("audio coverage: %.1f%% (%d/%d tracks)", coverage * 100, (manifest["status"] == "ok").sum(), len(manifest))
    if coverage < 0.5:
        log.warning(
            "Audio coverage is under 50%%. Per the project plan, consider falling "
            "back to metadata-only features (AcousticBrainz/Last.fm) for v1."
        )
    return manifest
