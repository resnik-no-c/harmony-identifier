# Playlist Vectorizer

Turn a Spotify playlist into a point in a shared feature space, then compute
its **centroid**, its **medoid** (the actual most-representative track), its
**dispersion** (how coherent the playlist is), and compare it against other
playlists. Full rationale and design decisions are in the project plan this
implements; the short version:

Spotify killed `audio_features`/`audio_analysis`/`Recommendations` for any
app registered after 27 Nov 2024 (and most apps still in development mode
before that date too). This pipeline routes around it: free metadata APIs +
the frozen AcousticBrainz dumps + your own Essentia/librosa analysis of
30-second audio previews, instead of Spotify's retired endpoint.

## Why this needs to run on your machine, not a cloud sandbox

Three things here can't run in a stateless container: the Spotify OAuth flow
needs a real browser hitting `127.0.0.1`, `essentia-tensorflow` is a heavy
native build that's picky about your Python/OS combo, and if you want to use
your own music library for Step 3 it has to actually be on disk. Clone this
branch locally and run the phases from there.

## Setup

```bash
cd playlist-vectorizer
python3.11 -m venv .venv        # 3.11/3.12 — essentia-tensorflow doesn't have
source .venv/bin/activate       # wheels for every Python version yet, check
pip install -e .                # essentia.upf.edu before picking one
cp .env.example .env
```

Fill in `.env`:
- `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET`: register a free app at
  https://developer.spotify.com/dashboard, redirect URI
  `http://127.0.0.1:8888/callback`.
- `LASTFM_API_KEY`: free, non-commercial, from https://www.last.fm/api/account/create.
- `MUSICBRAINZ_USER_AGENT`: required by MusicBrainz's API etiquette — put a
  real contact in it or they may throttle you.
- Everything else (`DISCOGS_TOKEN`, `ACOUSTICBRAINZ_DUMP_DIR`,
  `ESSENTIA_MODELS_DIR`) is optional; the pipeline degrades gracefully
  without them.

## Running the pipeline

Each command is one phase and writes a parquet checkpoint to `PV_DATA_DIR`
(default `./data`) so you can stop, re-run, and resume freely — nothing here
should ever force you to redo a 400-track run because of one crash.

```bash
pv export --playlist-id <spotify_playlist_id_or_uri>   # P1
pv enrich [--use-discogs]                                # P2
pv fetch-audio [--library-dir /path/to/your/music]       # P3
pv extract-features --engine librosa|essentia            # P4
pv vectorize                                             # P5 (encode)
pv centroid                                               # P5 (reduce)
pv analyze [--viz]                                        # P6
```

**Build against a 10-track test playlist first.** Every join bug, OAuth
expiry, and rate-limit surprise shows up at 10 tracks in seconds instead of
at 400 tracks an hour in.

### The P2/P3 decision point

`pv enrich` writes `data/coverage_report.json`. If
`acousticbrainz_highlevel_coverage` is above ~70%, the log will tell you so —
**P2 may be the whole project**: skip `fetch-audio`/`extract-features`
entirely and vectorize straight off the metadata block. AcousticBrainz
coverage skews toward pre-2022, well-catalogued releases, so this is playlist-
dependent; measure, don't assume.

To get AcousticBrainz's offline dumps: download the low-level + high-level
archives from https://acousticbrainz.org/download, extract them anywhere,
and point `ACOUSTICBRAINZ_DUMP_DIR` at the extraction root (any nesting is
fine — `pv` indexes by filename on first use and caches the index).

### Essentia vs. librosa for `extract-features`

`librosa` always works and needs no model downloads — use it as your
baseline. `essentia` gets you the specific pragmatic combination the plan
recommends (Discogs-EffNet embeddings + classifier heads), but:

- `essentia-tensorflow` install is genuinely finicky. If it won't build
  natively, Docker is the documented fallback rather than fighting your
  platform's wheel situation.
- The embedding + classifier-head models are downloaded separately from
  https://essentia.upf.edu/models.html into `ESSENTIA_MODELS_DIR`.
  **They are licensed CC BY-NC-SA 4.0 — non-commercial only.** `MusicExtractor`
  itself (no model files) has no such restriction. If this project's output
  ever leaves personal use, swap the classifier heads for CLAP or MERT
  (Apache-2.0) — see `features_essentia.py` for where those would plug in.
- Getting a classifier head's `positive_index` wrong silently flips a mood
  score. Check each model's metadata JSON on the models page rather than
  assuming class order — `ClassifierHead` in `features_essentia.py` makes
  this an explicit, per-model setting for exactly that reason.

## What you get

- **Medoid** — the actual track closest to the centroid. The only centroid
  variant you can literally listen to.
- **Least representative track** — furthest from the centroid; usually a
  mistake or the most interesting song on the playlist.
- **Coherence score** — mean distance to centroid, comparable across
  playlists once the feature space is fixed.
- **Per-block dispersion** — "tight on energy, scattered on genre" is a real
  finding this reveals that a single coherence number hides.
- **The unimodality check** — `pv centroid` always runs a silhouette sweep at
  k=2,3,4. If a k>1 solution wins, the honest output is *k centroids and
  their sizes*, not one centroid sitting in empty space between two real
  clusters. This is mandatory, not a nice-to-have — see
  `tests/test_centroid.py::test_silhouette_sweep_detects_two_clear_clusters`.
- **`pv analyze --viz`** — a UMAP plot with the centroid projected through
  the *same fitted transform* used for the tracks (never recomputed in 2D —
  UMAP doesn't preserve global geometry, so the visual center of the plot is
  not the centroid).

`analysis.py` also has `playlist_to_playlist_distance` (compare two
playlists as points), `rolling_centroid_drift` (taste over time via
`added_at`), and `subclusters` (k-means + tag-based cluster labeling) for
when the unimodality check says a playlist is really two playlists.

## How vectorization actually works (`vectorize.py`)

Per-attribute blocks, each encoded on its own terms, then combined:

| Block kind | Encoding |
| --- | --- |
| `acoustic_scalar` / `skewed` | quantile-transform to normal, then z-score |
| `probability` (mood, instrumentation) | left in [0,1], no scaling |
| `cyclic_key` | position on the **circle of fifths** (not chromatic index), sin/cos + major/minor flag |
| `tempo` | `log2(bpm) mod 1` — collapses double/half-tempo extractor disagreements |
| `tags` | TF-IDF over the tag vocabulary, then TruncatedSVD |
| `embedding` | L2-normalize, then PCA — reduced *before* combining with anything else |

After per-block scaling, each block is multiplied by `sqrt(weight / dim)` so
you control its share of total variance explicitly. Defaults
(`DEFAULT_WEIGHTS` in `vectorize.py`): embedding 0.40, acoustic scalars 0.25,
mood 0.15, genre tags 0.15, metadata/key/tempo 0.05 each. There's no correct
set of weights, only a documented one — change them and re-run to see how
much the centroid moves.

**Missing data is never zero-filled.** After z-scoring, zero is the mean —
silently dragging incomplete tracks toward the center and faking a tighter
playlist than you actually have. A block whose coverage falls under 60% is
dropped from the vector space entirely (logged when it happens); otherwise
missing values stay `NaN` and `centroid.py` consumes them directly via
`sklearn.metrics.pairwise.nan_euclidean_distances`, which scales each
pairwise distance by the fraction of dimensions actually present rather than
guessing. `vectorize.impute_iterative` is available for the few consumers
(k-means, UMAP) that require a fully dense matrix.

## Testing

```bash
pip install -e ".[dev]"
pytest tests/
```

The test suite covers the pure math — cyclic key/tempo encoding, block
dropping, NaN-preserving imputation, all four centroid variants, and the
silhouette-driven unimodality check — since that's the part correctness
actually depends on and the part that needs no network or credentials to
verify. `tests/smoke_e2e.py` is a manual (non-pytest) script that generates a
synthetic two-cluster playlist and runs `vectorize` → `centroid` → `analyze`
through the real CLI, for exercising the merge/CLI wiring without live APIs:

```bash
PV_DATA_DIR=/tmp/pv_smoke .venv/bin/python tests/smoke_e2e.py
PV_DATA_DIR=/tmp/pv_smoke pv vectorize && PV_DATA_DIR=/tmp/pv_smoke pv centroid --help
```

## Reference stack

| Layer | Tool | License |
| --- | --- | --- |
| Spotify export | [Spotipy](https://github.com/spotipy-dev/spotipy) | MIT |
| Metadata | [musicbrainzngs](https://github.com/alastair/python-musicbrainzngs), [pylast](https://github.com/pylast/pylast) | BSD-2, Apache-2.0 |
| Pre-computed features | [AcousticBrainz dumps](https://acousticbrainz.org/download) | CC0 |
| Audio features | [Essentia](https://essentia.upf.edu/) | AGPL-3.0 (library), **CC BY-NC-SA 4.0** (MTG pretrained models) |
| DSP fallback | [librosa](https://librosa.org/) | ISC |
| Vectorization | [scikit-learn](https://scikit-learn.org/) | BSD-3 |
| Storage | Parquet via pandas/pyarrow | BSD-3/Apache-2.0 |
| Projection | [umap-learn](https://umap-learn.readthedocs.io/) (optional) | BSD-3 |

## Known gaps / not implemented

- **Deezer preview resolution is unverified.** The plan flags this
  explicitly — `api.deezer.com/2.0/track/isrc:{isrc}` was the standard
  post-deprecation MIR workaround as of the plan's writing, but it's an
  unauthenticated third-party endpoint that can change without notice.
  Check `audio_fetch.py`'s behavior against real ISRCs before depending on
  it, and read Deezer's API terms for your use case.
- **CLAP/MERT embeddings** are not wired in — `features_essentia.py` has the
  Apache-2.0 swap-out point noted where the CC BY-NC-SA classifier heads
  would be replaced if this ever needs to be commercial-use-safe.
- **Streaming-source audio extraction (yt-dlp et al.) is deliberately not
  implemented.** It's technically trivial but against most platforms'
  terms of service — use your own library or Deezer previews instead.
- **Jamendo/FMA calibration corpus fetching** isn't built — the plan
  describes it as a way to test the pipeline before pointing it at real
  playlist audio; `audio_fetch.index_local_library` covers the "point it at
  music you already have" path, which is the cleaner option if you have one.
