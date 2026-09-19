# Quickstart (run this on your own machine)

This can't run in a cloud sandbox — it needs a real browser (Spotify login)
and unrestricted internet (MusicBrainz/Deezer/AcousticBrainz). Do this on
your laptop.

## 0. Prerequisites

- Python 3.11 or 3.12 (not 3.13 yet — essentia-tensorflow doesn't have wheels for it).
  Check: `python3 --version`
- A terminal and about 15 minutes for the first pass.

## 1. Unzip and set up the venv

```bash
cd ~/Downloads
unzip playlist-vectorizer.zip -d playlist-vectorizer
cd playlist-vectorizer
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Confirm it installed cleanly:

```bash
pytest tests/
```

You should see `16 passed`. This only exercises the pure math (no network,
no credentials) — it's just confirming the install worked before you touch
any live API.

## 2. Get a Spotify app (5 minutes, free)

1. Go to https://developer.spotify.com/dashboard, log in, click **Create app**.
2. App name/description: anything. Redirect URI: exactly
   `http://127.0.0.1:8888/callback` (must match character-for-character).
3. Save, then open the app and copy the **Client ID** and **Client secret**.

## 3. Get a Last.fm API key (2 minutes, free)

Go to https://www.last.fm/api/account/create, fill in the form (any app
name), submit. Copy the **API key**.

## 4. Configure

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in:

```
SPOTIPY_CLIENT_ID=<from step 2>
SPOTIPY_CLIENT_SECRET=<from step 2>
LASTFM_API_KEY=<from step 3>
MUSICBRAINZ_USER_AGENT=playlist-vectorizer/0.1 (your-real-email@example.com)
```

Leave everything else blank for now — `DISCOGS_TOKEN`,
`ACOUSTICBRAINZ_DUMP_DIR`, and `ESSENTIA_MODELS_DIR` are optional and the
pipeline works without them (see README for what each one adds).

## 5. Find a playlist ID to test with

Use a **small (~10 track) playlist first** — every bug shows up in seconds
at 10 tracks instead of an hour at 400. In Spotify: right-click a playlist →
Share → Copy link. The URL looks like:

```
https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
```

The ID is the part after `/playlist/` and before `?`: `37i9dQZF1DXcBWIGoYBM5M`.

## 6. Run it

```bash
pv export --playlist-id 37i9dQZF1DXcBWIGoYBM5M
```

Your browser will pop up asking you to log into Spotify and approve access
— that's the OAuth flow the plan describes; it only happens once (the token
is cached in `data/.spotify_token_cache`). Check the log line for ISRC
coverage; it should be well above 90% for a normal playlist.

```bash
pv enrich
```

Watch `data/coverage_report.json` afterward. If
`acousticbrainz_highlevel_coverage` is high, you may be able to skip straight
to vectorizing (see README's "P2/P3 decision point"). AcousticBrainz's dumps
aren't downloaded by default (`ACOUSTICBRAINZ_DUMP_DIR` unset), so on a first
run this will likely be 0% and that's expected — Last.fm tags still populate.

```bash
pv fetch-audio
pv extract-features --engine librosa
```

`librosa` needs no model downloads and works immediately. (Essentia is a
bigger install — see README's "Essentia vs. librosa" section if you want the
richer feature set later.)

```bash
pv vectorize
pv centroid
```

Check the log output: it names the medoid track (the actual song closest to
your playlist's center) and reports whether a silhouette sweep found your
playlist is secretly two clusters.

```bash
pip install -e ".[viz]"
pv analyze --viz
```

Open `data/umap.png` — you should see your tracks scattered with the
centroid marked as a red star.

## If something breaks

- **`SPOTIPY_CLIENT_ID / SPOTIPY_CLIENT_SECRET are not set`** — `.env` wasn't
  filled in, or you're not running from inside the `playlist-vectorizer`
  directory (dotenv loads `.env` relative to cwd).
- **Browser doesn't open for login** — copy the URL printed in the terminal
  into a browser manually.
- **`INVALID_CLIENT: Invalid redirect URI`** — the redirect URI in your
  Spotify app settings doesn't exactly match `http://127.0.0.1:8888/callback`.
- **Low ISRC coverage after `pv export`** — the playlist has a lot of local
  files or podcast episodes; pick a different test playlist.
- **`essentia is not installed`** — expected if you skipped `pip install
  ".[essentia]"`; use `--engine librosa` instead, or see the README for the
  Essentia install caveats.

Once the 10-track run works end to end, re-point `pv export` at your real
playlist and re-run the same commands — everything is resumable, so a crash
partway through just picks back up where it left off.
