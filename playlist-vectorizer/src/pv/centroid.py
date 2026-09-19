"""Step 5 — four centroid variants, dispersion, and the unimodality check.

The arithmetic mean is one line; knowing when it lies to you is the rest of
this module. All distance-based functions use `nan_euclidean_distances`
directly on vectors that may still carry NaN for dropped/missing blocks,
per scikit-learn's convention: it scales the squared distance by
(n_dims / n_present_dims) for each pair, rather than pretending a missing
dimension is zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import nan_euclidean_distances


def euclidean_mean(X: np.ndarray) -> np.ndarray:
    """Arithmetic mean, per dimension, ignoring NaN. The default centroid;
    valid when the playlist is roughly unimodal (see silhouette_sweep)."""
    return np.nanmean(X, axis=0)


def spherical_mean(X: np.ndarray) -> np.ndarray:
    """Mean of L2-normalized vectors, re-normalized. Use this when you care
    about direction (timbral/embedding character) rather than magnitude.
    Only fully-observed rows can be meaningfully normalized, so rows with
    any missing dimension are excluded from this one.
    """
    complete = X[~np.isnan(X).any(axis=1)]
    if len(complete) == 0:
        raise ValueError("no fully-observed rows to compute a spherical mean from")
    norms = np.linalg.norm(complete, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = complete / norms
    mean = unit.mean(axis=0)
    mean_norm = np.linalg.norm(mean)
    return mean / mean_norm if mean_norm > 0 else mean


def geometric_median(X: np.ndarray, tol: float = 1e-6, max_iter: int = 500) -> np.ndarray:
    """Weiszfeld's algorithm: minimizes sum of Euclidean distances to all
    points, which resists a few outlier tracks dragging the mean around.
    Computed on fully-observed rows (Weiszfeld's weighting breaks down with
    per-dimension missingness).
    """
    complete = X[~np.isnan(X).any(axis=1)]
    if len(complete) == 0:
        raise ValueError("no fully-observed rows to compute a geometric median from")

    guess = complete.mean(axis=0)
    for _ in range(max_iter):
        diffs = complete - guess
        dists = np.linalg.norm(diffs, axis=1)
        dists[dists < 1e-12] = 1e-12  # avoid divide-by-zero when guess lands on a point
        weights = 1.0 / dists
        new_guess = (complete * weights[:, None]).sum(axis=0) / weights.sum()
        if np.linalg.norm(new_guess - guess) < tol:
            return new_guess
        guess = new_guess
    return guess


def medoid_index(X: np.ndarray) -> int:
    """The actual track minimizing total distance to all others — the only
    centroid variant you can literally listen to. Always compute this one."""
    D = nan_euclidean_distances(X)
    return int(np.argmin(D.sum(axis=1)))


def mean_distance_to_centroid(X: np.ndarray, centroid: np.ndarray) -> float:
    """Playlist coherence: mean distance from every track to the centroid,
    in the same units as the feature space."""
    D = nan_euclidean_distances(X, centroid.reshape(1, -1))
    return float(np.nanmean(D))


def per_block_distance_to_centroid(
    X: np.ndarray, centroid: np.ndarray, block_slices: dict[str, slice]
) -> dict[str, float]:
    """Mean distance to centroid computed separately per block — a playlist
    can be tight on energy and scattered on genre, which is a real,
    interesting fact this single number hides."""
    return {
        name: mean_distance_to_centroid(X[:, sl], centroid[sl])
        for name, sl in block_slices.items()
    }


@dataclass
class SilhouetteResult:
    k: int
    score: float


def silhouette_sweep(X_dense: np.ndarray, ks: tuple[int, ...] = (2, 3, 4), random_state: int = 0) -> list[SilhouetteResult]:
    """Mandatory unimodality check, not optional. X_dense must be NaN-free
    (impute first, e.g. with `vectorize.impute_iterative`). If a k>1 solution
    scores well here, this playlist isn't one cluster and a single centroid
    doesn't summarize it — report k centroids instead (see project plan).
    """
    results = []
    n = len(X_dense)
    for k in ks:
        if k >= n:
            continue
        labels = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit_predict(X_dense)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(X_dense, labels)
        results.append(SilhouetteResult(k=k, score=float(score)))
    return results


def unimodal(results: list[SilhouetteResult], single_cluster_threshold: float = 0.15) -> bool:
    """True if no k>1 clustering beats a weak-structure threshold, i.e. the
    playlist is reasonably summarized by one centroid. This is a heuristic,
    not a proof — look at the UMAP plot too."""
    return all(r.score < single_cluster_threshold for r in results)


@dataclass
class CentroidReport:
    euclidean_mean: np.ndarray
    spherical_mean: np.ndarray | None
    geometric_median: np.ndarray | None
    medoid_index: int
    mean_distance_to_centroid: float
    per_block_distance: dict[str, float]
    silhouette: list[SilhouetteResult]
    is_unimodal: bool


def compute_all(
    X: np.ndarray,
    block_slices: dict[str, slice],
    X_dense_for_silhouette: np.ndarray | None = None,
    silhouette_ks: tuple[int, ...] = (2, 3, 4),
) -> CentroidReport:
    mean = euclidean_mean(X)

    try:
        sph = spherical_mean(X)
    except ValueError:
        sph = None
    try:
        gmed = geometric_median(X)
    except ValueError:
        gmed = None

    medoid_idx = medoid_index(X)
    mean_dist = mean_distance_to_centroid(X, mean)
    per_block = per_block_distance_to_centroid(X, mean, block_slices)

    silhouette = []
    if X_dense_for_silhouette is not None:
        silhouette = silhouette_sweep(X_dense_for_silhouette, ks=silhouette_ks)

    return CentroidReport(
        euclidean_mean=mean,
        spherical_mean=sph,
        geometric_median=gmed,
        medoid_index=medoid_idx,
        mean_distance_to_centroid=mean_dist,
        per_block_distance=per_block,
        silhouette=silhouette,
        is_unimodal=unimodal(silhouette) if silhouette else True,
    )
