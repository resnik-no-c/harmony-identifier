"""MusicBrainz: ISRC -> Recording MBID. The hinge of the whole design — MBID
is the join key into AcousticBrainz, ListenBrainz, and Discogs release data.

Rate limit is 1 req/sec and a descriptive User-Agent is mandatory, or
MusicBrainz will start throttling/blocking the IP.
"""

from __future__ import annotations

import logging

import musicbrainzngs as mb

from .cache import DiskCache, RateLimiter
from .config import Config

log = logging.getLogger(__name__)

_configured = False


def _configure(cfg: Config) -> None:
    global _configured
    if _configured:
        return
    mb.set_useragent(*_split_user_agent(cfg.musicbrainz_user_agent))
    _configured = True


def _split_user_agent(ua: str) -> tuple[str, str, str]:
    # "name/version (contact)" -> (name, version, contact)
    name_version, _, contact = ua.partition("(")
    name, _, version = name_version.strip().partition("/")
    return name or "playlist-vectorizer", version.strip() or "0.1", contact.rstrip(") ").strip()


def isrc_to_mbid(cfg: Config, isrc: str, cache: DiskCache, limiter: RateLimiter) -> str | None:
    """Return the first recording MBID for an ISRC, or None if unmatched.

    A single ISRC can map to multiple recordings (remasters, regional
    releases); we take the first result and leave dedup/verification to the
    caller — cheap ISRC collisions are a known pitfall (see README).
    """
    cached = cache.get(isrc)
    if cached is not None:
        return cached.get("mbid")

    _configure(cfg)
    limiter.wait()
    try:
        result = mb.get_recordings_by_isrc(isrc)
    except mb.ResponseError:
        cache.set(isrc, {"mbid": None})
        return None
    except Exception as exc:  # noqa: BLE001 - network flakiness shouldn't kill a 400-track run
        log.warning("MusicBrainz lookup failed for %s: %s", isrc, exc)
        return None

    recordings = result.get("isrc", {}).get("recording-list", [])
    mbid = recordings[0]["id"] if recordings else None
    cache.set(isrc, {"mbid": mbid, "candidate_count": len(recordings)})
    return mbid
