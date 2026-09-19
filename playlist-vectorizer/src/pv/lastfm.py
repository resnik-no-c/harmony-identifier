"""Last.fm community tags — a free, non-commercial-use view of genre/vibe
that AcousticBrainz and Spotify's remaining endpoints don't give you."""

from __future__ import annotations

import logging

import pylast

from .cache import DiskCache, RateLimiter
from .config import Config

log = logging.getLogger(__name__)

_network: pylast.LastFMNetwork | None = None


def _get_network(cfg: Config) -> pylast.LastFMNetwork:
    global _network
    if _network is None:
        if not cfg.lastfm_api_key:
            raise SystemExit("LASTFM_API_KEY is not set (see .env.example).")
        _network = pylast.LastFMNetwork(api_key=cfg.lastfm_api_key, api_secret=cfg.lastfm_api_secret or "")
    return _network


def top_tags(
    cfg: Config, artist: str, title: str, cache: DiskCache, limiter: RateLimiter, limit: int = 10
) -> list[tuple[str, int]]:
    """Return up to `limit` (tag, weight) pairs for a track, weight in [0, 100]."""
    key = f"{artist}::{title}"
    cached = cache.get(key)
    if cached is not None:
        return [tuple(t) for t in cached]

    network = _get_network(cfg)
    limiter.wait()
    try:
        track = network.get_track(artist, title)
        tags = track.get_top_tags(limit=limit)
        result = [(t.item.get_name(), int(t.weight)) for t in tags]
    except Exception as exc:  # noqa: BLE001
        log.warning("Last.fm lookup failed for %r - %r: %s", artist, title, exc)
        result = []

    cache.set(key, result)
    return result
