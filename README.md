# UkasCoUmis

A chaotic little **Pygame music player**.

- Left side: album art + simple visualization + transport controls
- Right side: library list (music + videos/audio)
- Extras: background “cat moshpit” sprites that react to the track energy

> This repo is a small hobby project / GUI toy. Expect rough edges.

## Features

- Play local audio from `./library/`
- Play audio extracted/downloaded from YouTube via `yt-dlp`
- Basic search/filter
- Progress bar seeking (click to jump)
- Volume knob
- Auto-reads metadata + tries to fetch/resolve album art
- Reactive visuals + moshpit sprites

## Project structure

```
.
├─ main.py              # app entrypoint
├─ library.py           # library indexing/render items
├─ library/             # your music downloads (mp3)
├─ videos/              # optional: downloaded “videos audio”
├─ *.png                # UI images
└─ requirements.txt
```

## Requirements

- Python 3.11+ recommended
- Windows tested (should also run on Linux/macOS if dependencies are available)

Python deps are listed in `requirements.txt`.

### Notes on optional deps

The app will run with **just** `pygame`, but some features need extra packages:

- `mutagen`: track length + tag reading
- `requests`: album art fetching
- `yt-dlp`: YouTube downloads
- `numpy` + `soundfile` / `pydub`: better audio-energy visualization (PCM-based)
    - `pydub` typically requires **ffmpeg** installed and available on PATH

## Installation

Create a venv and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Usage

- Click a song in the right-side library to play it.
- Space: play/pause
- Left/Right arrows: seek -5s/+5s
- Click the progress bar to jump
- Drag the volume knob to change volume
- Paste a YouTube link in the download box (bottom-right) and press Enter.

## Screenshots

> Put the images in `./screenshots/` with these exact filenames.

### Home (idle)

![Home (idle)](screenshots/01-home-idle.png)

### Playing (visuals + cats)

![Playing](screenshots/02-playing-visuals.png)

## Troubleshooting

### `pydub` errors / no decoding

Install ffmpeg:
- Windows: `winget install Gyan.FFmpeg`
- Or download from https://ffmpeg.org/ and add to PATH

### `soundfile` install fails

On Windows it usually works via wheels. If not, try upgrading pip:

```powershell
python -m pip install --upgrade pip
```

## License

No license file yet. If you plan to share/fork publicly, add a license (MIT/Apache-2.0/etc.).


