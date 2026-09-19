"""Discogs genre/style taxonomy — optional, coarser than Last.fm tags but a
clean controlled vocabulary. Skipped entirely if DISCOGS_TOKEN is unset."""

from __future__ import annotations

import logging

import requests

from .cache import DiskCache, RateLimiter
from .config import Config

log = logging.getLogger(__name__)

_SEARCH_URL = "https://api.discogs.com/database/search"


def genres_and_styles(
    cfg: Config, artist: str, title: str, cache: DiskCache, limiter: RateLimiter
) -> dict[str, list[str]]:
    if not cfg.discogs_token:
        return {"genres": [], "styles": []}

    key = f"{artist}::{title}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    limiter.wait()
    try:
        resp = requests.get(
            _SEARCH_URL,
            params={"artist": artist, "track": title, "type": "release", "token": cfg.discogs_token},
            headers={"User-Agent": cfg.musicbrainz_user_agent},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        result = {
            "genres": sorted({g for r in results[:3] for g in r.get("genre", [])}),
            "styles": sorted({s for r in results[:3] for s in r.get("style", [])}),
        }
    except requests.RequestException as exc:
        log.warning("Discogs lookup failed for %r - %r: %s", artist, title, exc)
        result = {"genres": [], "styles": []}

    cache.set(key, result)
    return result
