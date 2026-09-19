import numpy as np
import pytest

from pv.centroid import (
    euclidean_mean,
    geometric_median,
    medoid_index,
    mean_distance_to_centroid,
    per_block_distance_to_centroid,
    silhouette_sweep,
    spherical_mean,
    unimodal,
    SilhouetteResult,
)


def test_euclidean_mean_ignores_nan_not_zero():
    X = np.array([[1.0, 2.0], [3.0, np.nan], [5.0, 6.0]])
    mean = euclidean_mean(X)
    assert mean[0] == pytest.approx(3.0)
    assert mean[1] == pytest.approx(4.0)  # not (2+0+6)/3


def test_medoid_is_the_most_central_point():
    # A tight cluster around the origin plus one far outlier.
    rng = np.random.default_rng(0)
    cluster = rng.normal(scale=0.1, size=(9, 3))
    outlier = np.array([[50.0, 50.0, 50.0]])
    X = np.vstack([cluster, outlier])
    idx = medoid_index(X)
    assert idx != 9  # the outlier should never be the medoid


def test_geometric_median_resists_outliers_more_than_mean():
    X = np.array([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0], [100.0, 100.0]])
    mean = euclidean_mean(X)
    gmed = geometric_median(X)
    # The mean gets dragged hard toward the outlier; the geometric median should not.
    assert np.linalg.norm(gmed - np.array([0.5, 0.5])) < np.linalg.norm(mean - np.array([0.5, 0.5]))


def test_spherical_mean_is_unit_norm():
    X = np.array([[3.0, 4.0], [1.0, 0.0], [0.0, 1.0]])
    mean = spherical_mean(X)
    assert np.linalg.norm(mean) == pytest.approx(1.0)


def test_mean_distance_to_centroid_is_zero_for_identical_points():
    X = np.ones((5, 4))
    centroid = euclidean_mean(X)
    assert mean_distance_to_centroid(X, centroid) == pytest.approx(0.0, abs=1e-9)


def test_per_block_distance_reports_each_block_separately():
    X = np.array([[0.0, 0.0, 10.0], [0.0, 0.0, -10.0]])
    centroid = euclidean_mean(X)
    slices = {"tight": slice(0, 2), "scattered": slice(2, 3)}
    result = per_block_distance_to_centroid(X, centroid, slices)
    assert result["tight"] == pytest.approx(0.0, abs=1e-9)
    assert result["scattered"] > 5.0


def test_silhouette_sweep_detects_two_clear_clusters():
    rng = np.random.default_rng(1)
    cluster_a = rng.normal(loc=[-5, -5], scale=0.2, size=(20, 2))
    cluster_b = rng.normal(loc=[5, 5], scale=0.2, size=(20, 2))
    X = np.vstack([cluster_a, cluster_b])
    results = silhouette_sweep(X, ks=(2, 3, 4))
    best = max(results, key=lambda r: r.score)
    assert best.k == 2
    assert best.score > 0.8
    assert not unimodal(results)


def test_unimodal_true_when_no_real_structure():
    weak_results = [SilhouetteResult(k=2, score=0.05), SilhouetteResult(k=3, score=0.02)]
    assert unimodal(weak_results)
