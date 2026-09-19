"""Environment and path configuration, loaded once from .env / the shell."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _root() -> Path:
    root = Path(os.environ.get("PV_DATA_DIR", "./data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class Config:
    data_dir: Path
    cache_dir: Path
    audio_dir: Path

    spotify_client_id: str | None
    spotify_client_secret: str | None
    spotify_redirect_uri: str

    lastfm_api_key: str | None
    lastfm_api_secret: str | None

    discogs_token: str | None

    musicbrainz_user_agent: str

    acousticbrainz_dump_dir: Path | None
    essentia_models_dir: Path | None

    @property
    def tracks_path(self) -> Path:
        return self.data_dir / "tracks.parquet"

    @property
    def features_metadata_path(self) -> Path:
        return self.data_dir / "features_metadata.parquet"

    @property
    def manifest_path(self) -> Path:
        return self.data_dir / "manifest.parquet"

    @property
    def features_audio_path(self) -> Path:
        return self.data_dir / "features_audio.parquet"

    @property
    def vectors_path(self) -> Path:
        return self.data_dir / "vectors.parquet"

    @property
    def centroids_path(self) -> Path:
        return self.data_dir / "centroids.json"


def load_config() -> Config:
    data_dir = _root()
    ab_dir = os.environ.get("ACOUSTICBRAINZ_DUMP_DIR") or None
    models_dir = os.environ.get("ESSENTIA_MODELS_DIR") or None
    return Config(
        data_dir=data_dir,
        cache_dir=data_dir / "cache",
        audio_dir=data_dir / "audio",
        spotify_client_id=os.environ.get("SPOTIPY_CLIENT_ID") or None,
        spotify_client_secret=os.environ.get("SPOTIPY_CLIENT_SECRET") or None,
        spotify_redirect_uri=os.environ.get(
            "SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
        ),
        lastfm_api_key=os.environ.get("LASTFM_API_KEY") or None,
        lastfm_api_secret=os.environ.get("LASTFM_API_SECRET") or None,
        discogs_token=os.environ.get("DISCOGS_TOKEN") or None,
        musicbrainz_user_agent=os.environ.get(
            "MUSICBRAINZ_USER_AGENT", "playlist-vectorizer/0.1 (unset-contact)"
        ),
        acousticbrainz_dump_dir=Path(ab_dir).resolve() if ab_dir else None,
        essentia_models_dir=Path(models_dir).resolve() if models_dir else None,
    )
