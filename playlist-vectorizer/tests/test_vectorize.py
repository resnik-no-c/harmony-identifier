import numpy as np
import pandas as pd
import pytest

from pv.vectorize import (
    BlockSpec,
    Vectorizer,
    circle_of_fifths_position,
    cyclic_key_encode,
    fold_tempo_octave,
    impute_iterative,
)


def test_circle_of_fifths_position_matches_known_order():
    # C, G, D, A, E, B, F#, C#, G#, D#, A#, F at steps 0..11
    expected = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6, 1: 7, 8: 8, 3: 9, 10: 10, 5: 11}
    for pitch_class, position in expected.items():
        assert circle_of_fifths_position(np.array([pitch_class]))[0] == position


def test_cyclic_key_encoding_puts_fifths_neighbors_closer_than_chromatic_neighbors():
    # C (0) and G (7) are a fifth apart (harmonically close);
    # C (0) and B (11) are a semitone apart chromatically but far on the circle of fifths.
    c = cyclic_key_encode(np.array([0]), np.array([1]))[0, :2]
    g = cyclic_key_encode(np.array([7]), np.array([1]))[0, :2]
    b = cyclic_key_encode(np.array([11]), np.array([1]))[0, :2]

    dist_c_g = np.linalg.norm(c - g)
    dist_c_b = np.linalg.norm(c - b)
    assert dist_c_g < dist_c_b


def test_fold_tempo_octave_collapses_double_time():
    folded_85 = fold_tempo_octave(np.array([85.0]))[0, 0]
    folded_170 = fold_tempo_octave(np.array([170.0]))[0, 0]
    assert folded_85 == pytest.approx(folded_170, abs=1e-9)


def test_vectorizer_drops_low_coverage_block_and_keeps_high_coverage_one():
    n = 20
    df = pd.DataFrame(
        {
            "good_scalar": np.random.randn(n),
            "sparse_scalar": [np.nan] * 15 + list(np.random.randn(5)),  # 25% coverage
        }
    )
    specs = [
        BlockSpec("good", ["good_scalar"], "acoustic_scalar", 0.5),
        BlockSpec("sparse", ["sparse_scalar"], "acoustic_scalar", 0.5),
    ]
    vectorizer = Vectorizer(specs)
    X = vectorizer.fit_transform(df)

    assert "good" in vectorizer.block_slices
    assert "sparse" not in vectorizer.block_slices
    assert X.shape == (n, 1)


def test_vectorizer_never_zero_fills_missing_rows():
    n = 10
    df = pd.DataFrame({"scalar": [1.0, 2.0, 3.0, np.nan, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]})
    specs = [BlockSpec("block", ["scalar"], "acoustic_scalar", 1.0)]
    vectorizer = Vectorizer(specs)
    X = vectorizer.fit_transform(df)

    # The missing row must stay NaN, not become 0 (which would be the mean
    # after z-scoring and would silently drag it toward the centroid).
    assert np.isnan(X[3, 0])
    assert not np.isnan(X[0, 0])


def test_impute_iterative_removes_all_nans():
    X = np.array([[1.0, np.nan], [2.0, 2.0], [3.0, 3.0], [np.nan, 4.0]])
    filled = impute_iterative(X)
    assert not np.isnan(filled).any()


def test_embedding_block_reduces_dimension_before_combining():
    n = 20
    dim = 64
    df = pd.DataFrame({"emb": [list(np.random.randn(dim)) for _ in range(n)]})
    specs = [BlockSpec("embedding", ["emb"], "embedding", 1.0, reduce_dim=5)]
    vectorizer = Vectorizer(specs)
    X = vectorizer.fit_transform(df)
    assert X.shape == (n, 5)


def test_tags_block_reduces_via_svd():
    n = 12
    vocab = ["rock", "pop", "jazz", "ambient", "folk", "metal"]
    tag_lists = [list(np.random.choice(vocab, size=3, replace=False)) for _ in range(n)]
    df = pd.DataFrame({"tags": tag_lists})
    specs = [BlockSpec("genre", ["tags"], "tags", 1.0, reduce_dim=3)]
    vectorizer = Vectorizer(specs)
    X = vectorizer.fit_transform(df)
    assert X.shape == (n, 3)
