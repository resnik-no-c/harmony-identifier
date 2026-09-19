"""Step 6 — turn the vector space + centroids into things a person can look
at and use: nearest/furthest track, playlist drift, sub-clusters, and plots.

UMAP/matplotlib are optional (`pip install '.[viz]'`) and lazy-imported so
the rest of the package doesn't need them.

The one rule that matters here: **never compute the centroid in the 2D
projection.** UMAP does not preserve global geometry, so the visual center
of a UMAP plot is not the centroid. Always compute centroids in full
dimensions (centroid.py) and project them into 2D with the *same fitted*
UMAP transform used for the tracks, via `project_point`.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from .centroid import mean_distance_to_centroid


def most_and_least_representative(
    df: pd.DataFrame, X: np.ndarray, centroid: np.ndarray, id_columns: list[str]
) -> tuple[pd.Series, pd.Series]:
    from sklearn.metrics.pairwise import nan_euclidean_distances

    distances = nan_euclidean_distances(X, centroid.reshape(1, -1)).ravel()
    most = df.iloc[int(np.nanargmin(distances))][id_columns]
    least = df.iloc[int(np.nanargmax(distances))][id_columns]
    return most, least


def playlist_to_playlist_distance(centroid_a: np.ndarray, centroid_b: np.ndarray) -> float:
    """Each playlist collapses to one point (its centroid); this is the
    distance between two playlists in the shared feature space."""
    return mean_distance_to_centroid(centroid_a.reshape(1, -1), centroid_b)


def rolling_centroid_drift(
    df: pd.DataFrame, X: np.ndarray, added_at_column: str = "added_at", min_window: int = 10
) -> pd.DataFrame:
    """Centroid computed over an expanding window of tracks in the order
    they were added, so you can see a playlist's taste move over time."""
    order = df[added_at_column].fillna(pd.Timestamp.min).argsort().to_numpy()
    rows = []
    for i in range(min_window, len(order) + 1):
        idx = order[:i]
        centroid = np.nanmean(X[idx], axis=0)
        rows.append({"n_tracks": i, "as_of": df.iloc[order[i - 1]][added_at_column], "centroid": centroid})
    return pd.DataFrame(rows)


def fit_umap(X_dense: np.ndarray, metric: str = "euclidean", random_state: int = 0):
    import umap

    reducer = umap.UMAP(metric=metric, random_state=random_state)
    embedding = reducer.fit_transform(X_dense)
    return reducer, embedding


def project_point(reducer, point: np.ndarray) -> np.ndarray:
    """Project a point (e.g. a centroid) through an *already-fitted* UMAP
    reducer. Do not refit — this is what keeps the projected centroid
    honest relative to the track embedding it's drawn alongside."""
    return reducer.transform(point.reshape(1, -1))[0]


def subclusters(
    X_dense: np.ndarray, k: int, tag_lists: pd.Series | None = None, random_state: int = 0
) -> tuple[np.ndarray, dict[int, list[str]]]:
    """k-means sub-clustering, with clusters labeled by their most
    distinctive tags (frequency inside the cluster vs. overall) when a tag
    column is supplied. This is usually where a playlist reveals its actual
    structure once the silhouette sweep says k>1 fits better than k=1."""
    labels = KMeans(n_clusters=k, n_init=10, random_state=random_state).fit_predict(X_dense)

    cluster_labels: dict[int, list[str]] = {}
    if tag_lists is not None:
        overall = Counter(t for tags in tag_lists for t in (tags or []))
        overall_total = sum(overall.values()) or 1
        for c in range(k):
            in_cluster = Counter(t for tags in tag_lists[labels == c] for t in (tags or []))
            cluster_total = sum(in_cluster.values()) or 1
            scored = sorted(
                in_cluster,
                key=lambda t: (in_cluster[t] / cluster_total) / (overall[t] / overall_total + 1e-9),
                reverse=True,
            )
            cluster_labels[c] = scored[:5]

    return labels, cluster_labels


def radar_chart(
    track_series: dict[str, dict[str, float]],
    output_path: str,
    title: str = "Playlist scalar features",
) -> None:
    """A radar/polar chart over interpretable scalar features (8-10 of them),
    centroid as one polygon with individual tracks overlaid — the plot that
    actually communicates a playlist to another person.

    `track_series` maps a label (e.g. "centroid", or a track title) to a
    dict of {feature_name: value_in_0_1}. Scale inputs to [0,1] before
    calling this (e.g. min-max per feature across the playlist).
    """
    import matplotlib.pyplot as plt

    feature_names = list(next(iter(track_series.values())).keys())
    n = len(feature_names)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for label, values in track_series.items():
        vals = [values[f] for f in feature_names]
        vals += vals[:1]
        is_centroid = label.lower() == "centroid"
        ax.plot(angles, vals, linewidth=2.5 if is_centroid else 1, label=label, alpha=1.0 if is_centroid else 0.5)
        if is_centroid:
            ax.fill(angles, vals, alpha=0.15)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(feature_names)
    ax.set_title(title)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
