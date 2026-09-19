"""Step 4 orchestrator — batched, resumable feature extraction over
manifest.parquet (audio the previous stage actually resolved). Writes
features_audio.parquet, one row per ISRC, keyed so a crash at track 340
resumes at 341 instead of redoing the whole run.
"""

from __future__ import annotations

import logging

import pandas as pd
from tqdm import tqdm

from .config import Config

log = logging.getLogger(__name__)


def run(cfg: Config, engine: str = "librosa") -> pd.DataFrame:
    if engine not in ("librosa", "essentia"):
        raise ValueError("engine must be 'librosa' or 'essentia'")

    manifest = pd.read_parquet(cfg.manifest_path)
    available = manifest[(manifest["status"] == "ok") & manifest["path"].notna()]

    existing = (
        pd.read_parquet(cfg.features_audio_path)
        if cfg.features_audio_path.exists()
        else pd.DataFrame(columns=["isrc"])
    )
    done = set(existing["isrc"]) if not existing.empty else set()

    if engine == "essentia":
        from . import features_essentia as extractor_mod

        def extract_one(path: str) -> dict:
            return extractor_mod.extract_all(path, cfg.essentia_models_dir)

    else:
        from . import features_librosa as extractor_mod

        def extract_one(path: str) -> dict:
            return extractor_mod.extract(path)

    rows = []
    failures = 0
    for _, item in tqdm(available.iterrows(), total=len(available), desc=f"extract ({engine})"):
        if item["isrc"] in done:
            continue
        try:
            feats = extract_one(item["path"])
            feats["isrc"] = item["isrc"]
            rows.append(feats)
        except Exception as exc:  # noqa: BLE001 - one bad file shouldn't kill a long batch
            log.warning("feature extraction failed for %s (%s): %s", item["isrc"], item["path"], exc)
            failures += 1

    new_features = pd.DataFrame(rows)
    combined = pd.concat([existing, new_features], ignore_index=True).drop_duplicates(
        subset="isrc", keep="last"
    )
    combined.to_parquet(cfg.features_audio_path, index=False)
    log.info(
        "extracted features for %d tracks (%d new, %d failed)", len(combined), len(rows), failures
    )
    return combined
