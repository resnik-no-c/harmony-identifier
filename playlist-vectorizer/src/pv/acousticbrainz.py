"""Offline lookup into the (now-frozen) AcousticBrainz data dumps.

AcousticBrainz stopped accepting submissions in 2022, but the final dumps are
still downloadable from https://acousticbrainz.org/download: low-level and
high-level Essentia output as JSON, keyed by MusicBrainz Recording MBID,
sharded into per-file JSON like `<mbid>-0.json` across many directories.

Expected layout after extracting the archives under ACOUSTICBRAINZ_DUMP_DIR:

    ACOUSTICBRAINZ_DUMP_DIR/
        lowlevel/**/<mbid>-*.json
        highlevel/**/<mbid>-*.json

(any nesting works — we index by filename, not by directory structure). This
is a fast, free, offline first pass; coverage skews toward pre-2022,
well-catalogued releases, so expect real misses on anything recent or obscure.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_INDEX_FILENAME = "_mbid_index.json"


def build_index(dump_dir: Path, force: bool = False) -> dict[str, dict[str, str]]:
    """Walk the dump directory once and cache mbid -> {low_level, high_level} paths."""
    index_path = dump_dir / _INDEX_FILENAME
    if index_path.exists() and not force:
        return json.loads(index_path.read_text())

    log.info("indexing AcousticBrainz dump under %s (one-time cost)", dump_dir)
    index: dict[str, dict[str, str]] = {}
    for path in dump_dir.rglob("*.json"):
        if path.name == _INDEX_FILENAME:
            continue
        # filenames look like "<mbid>-0.json"; mbid is a fixed-format UUID.
        stem = path.stem
        mbid = stem[:36]
        if len(mbid) != 36:
            continue
        kind = "low_level" if "lowlevel" in str(path).lower() else "high_level"
        index.setdefault(mbid, {})[kind] = str(path)

    index_path.write_text(json.dumps(index))
    log.info("indexed %d MBIDs", len(index))
    return index


_MOOD_KEYS = ["mood_happy", "mood_sad", "mood_aggressive", "mood_relaxed", "mood_party", "mood_electronic", "mood_acoustic"]


def _positive_prob(hl_entry: dict, positive_label: str) -> float | None:
    all_probs = hl_entry.get("all")
    if isinstance(all_probs, dict) and positive_label in all_probs:
        return all_probs[positive_label]
    value, prob = hl_entry.get("value"), hl_entry.get("probability")
    if value is None or prob is None:
        return None
    return prob if value == positive_label else 1 - prob


def lookup(index: dict[str, dict[str, str]], mbid: str) -> dict | None:
    paths = index.get(mbid)
    if not paths:
        return None

    features: dict = {"ab_mbid": mbid}

    if "low_level" in paths:
        try:
            ll = json.loads(Path(paths["low_level"]).read_text())
        except (OSError, json.JSONDecodeError):
            ll = {}
        features["ab_bpm"] = ll.get("rhythm", {}).get("bpm")
        features["ab_key"] = ll.get("tonal", {}).get("key_key")
        features["ab_scale"] = ll.get("tonal", {}).get("key_scale")
        features["ab_loudness"] = ll.get("lowlevel", {}).get("average_loudness")
        features["ab_dynamic_complexity"] = ll.get("lowlevel", {}).get("dynamic_complexity")

    if "high_level" in paths:
        try:
            hl_doc = json.loads(Path(paths["high_level"]).read_text())
        except (OSError, json.JSONDecodeError):
            hl_doc = {}
        hl = hl_doc.get("highlevel", {})
        if "danceability" in hl:
            features["ab_danceability"] = _positive_prob(hl["danceability"], "danceable")
        for mood_key in _MOOD_KEYS:
            if mood_key in hl:
                positive = mood_key.removeprefix("mood_")
                features[f"ab_{mood_key}"] = _positive_prob(hl[mood_key], positive)
        if "genre_rosamerica" in hl:
            features["ab_genre"] = hl["genre_rosamerica"].get("value")
            features["ab_genre_probability"] = hl["genre_rosamerica"].get("probability")

    return features
