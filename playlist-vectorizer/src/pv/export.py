"""Step 1 — export a playlist to tracks.parquet.

One row per track: Spotify ID, ISRC, title, artist(s), album, release date,
duration, popularity, explicit flag, artist genres, added_at. Local files and
unavailable tracks (null IDs) are dropped here so they can't poison joins
downstream. Stop here — this stage should not grow tendrils into stage 2.
"""

from __future__ import annotations

import logging

import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import Config

log = logging.getLogger(__name__)

SCOPE = "playlist-read-private playlist-read-collaborative"


def get_client(cfg: Config) -> spotipy.Spotify:
    if not cfg.spotify_client_id or not cfg.spotify_client_secret:
        raise SystemExit(
            "SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET are not set. "
            "Register an app at https://developer.spotify.com/dashboard and "
            "put its credentials in .env (see .env.example)."
        )
    # spotipy writes its token cache next to the cwd by default; keep it in
    # our data dir instead so a fresh checkout doesn't force a re-auth.
    auth = SpotifyOAuth(
        client_id=cfg.spotify_client_id,
        client_secret=cfg.spotify_client_secret,
        redirect_uri=cfg.spotify_redirect_uri,
        scope=SCOPE,
        cache_path=str(cfg.data_dir / ".spotify_token_cache"),
    )
    return spotipy.Spotify(auth_manager=auth)


def _batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def export_playlist(cfg: Config, playlist_id: str) -> pd.DataFrame:
    sp = get_client(cfg)

    raw_items: list[dict] = []
    offset = 0
    while True:
        page = sp.playlist_items(
            playlist_id,
            limit=100,
            offset=offset,
            additional_types=("track",),
        )
        raw_items.extend(page["items"])
        if page["next"] is None:
            break
        offset += 100
    log.info("fetched %d playlist items", len(raw_items))

    rows = []
    for item in raw_items:
        track = item.get("track")
        if track is None or track.get("id") is None:
            # Local files and region-unavailable tracks show up with null IDs.
            continue
        isrc = (track.get("external_ids") or {}).get("isrc")
        rows.append(
            {
                "spotify_id": track["id"],
                "isrc": isrc,
                "title": track["name"],
                "artist_ids": [a["id"] for a in track["artists"] if a.get("id")],
                "artist_names": [a["name"] for a in track["artists"]],
                "album": track["album"]["name"],
                "release_date": track["album"].get("release_date"),
                "duration_ms": track["duration_ms"],
                "popularity": track.get("popularity"),
                "explicit": track.get("explicit"),
                "added_at": item.get("added_at"),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("Playlist export produced zero usable tracks. Check the playlist ID/access.")

    df = df.drop_duplicates(subset="isrc", keep="first")

    # Batch artist lookups (max 50/call) to pull genre tags.
    all_artist_ids = sorted({aid for ids in df["artist_ids"] for aid in ids})
    genre_by_artist: dict[str, list[str]] = {}
    for chunk in _batched(all_artist_ids, 50):
        resp = sp.artists(chunk)
        for artist in resp["artists"]:
            genre_by_artist[artist["id"]] = artist.get("genres", [])

    df["artist_genres"] = df["artist_ids"].apply(
        lambda ids: sorted({g for aid in ids for g in genre_by_artist.get(aid, [])})
    )

    null_isrc_rate = df["isrc"].isna().mean()
    log.info("ISRC coverage: %.1f%%", (1 - null_isrc_rate) * 100)
    if null_isrc_rate > 0.10:
        log.warning(
            "Over 10%% of tracks have no ISRC. If this playlist is mostly "
            "local files, the rest of the pipeline has little to join against."
        )

    return df.reset_index(drop=True)


def save(df: pd.DataFrame, cfg: Config) -> None:
    df.to_parquet(cfg.tracks_path, index=False)
    df.to_csv(cfg.data_dir / "tracks.csv", index=False)
    log.info("wrote %s (%d rows)", cfg.tracks_path, len(df))
