"""A dumb, transparent disk cache: one JSON file per (namespace, key).

The point isn't speed, it's making every external call resumable. Re-running
the pipeline after a crash at track 340 should not re-hit any API for tracks
1-339. Keys are ISRCs almost everywhere, which also makes the cache directory
directly greppable/debuggable.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable


class DiskCache:
    def __init__(self, root: Path, namespace: str):
        self.dir = root / namespace
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are usually short IDs (ISRC/MBID), but hash defensively in case
        # something with slashes/unicode ends up here.
        safe = key if key.isascii() and "/" not in key else hashlib.sha1(key.encode()).hexdigest()
        return self.dir / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        p = self._path(key)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value))
        tmp.replace(p)  # atomic on POSIX; avoids truncated cache entries on crash

    def get_or_fetch(self, key: str, fetch: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = fetch()
        self.set(key, value)
        return value

    def __contains__(self, key: str) -> bool:
        return self._path(key).exists()


class RateLimiter:
    """Blocking rate limiter for polite use of free APIs (MusicBrainz: 1 req/s)."""

    def __init__(self, min_interval_seconds: float):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()
