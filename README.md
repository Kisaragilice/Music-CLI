# Music-CLI

A fast, keyboard-driven terminal music player — streaming via `yt-dlp` + `mpv`, inspired by [`spotify-player`](https://github.com/aome510/spotify-player).

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/terminal-TUI%20%7C%20no%20GUI-informational?style=flat-square" alt="TUI" />
  <img src="https://img.shields.io/badge/audio-mpv%20%7C%20yt--dlp-1DB954?style=flat-square" alt="mpv + yt-dlp" />
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="MIT" />
</p>

> **No Spotify Premium. No API keys.** Search and stream from YouTube / YouTube Music with a `spotify-player`-like TUI.

---

## Table of Contents

- [Features](#features)
- [Demo](#demo)
- [Requirements](#requirements)
- [Installation](#installation)
  - [Arch Linux (Recommended)](#arch-linux-recommended)
  - [Other Distros](#other-distros)
  - [Development Install](#development-install)
- [Usage](#usage)
- [Keybindings](#keybindings)
- [Configuration](#configuration)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [License](#license)

---

## Features

- **Search** YouTube Music via `ytmusicapi` (`filter=songs`, structured artists/albums) with `yt-dlp` fallback — no API key needed
- **Streaming** audio-only via `mpv --no-video --ytdl-format=bestaudio` (handles DASH, true streaming, no download)
- **TUI** built with [Textual](https://github.com/Textualize/textual) — paging, popups, vim-style navigation, mouse support
- **Queue** with shuffle / repeat (`off/all/one`), dedup, auto-next on EOF, **autoplay radio** (YouTube Music `get_watch_playlist` with `WEB_REMIX`, log-scale diverse mixes — not keyword search)
- **Audio visualization** — 64 log-scale bars (bass left → treble right), 8 rows bottom-up, green→blue gradient, peak at bar ~20 like `spotify-player`; real FFT via `parec`/`pw-record` + `numpy` fallback to smooth animated bars; `v` toggle
- **Cover art** — thumbnails cached in `~/.cache/music-cli/covers`, rendered via Kitty graphics protocol when available, otherwise colored half-blocks `▀` (works in any terminal); pixelate control `cover_pixels` (8..720) like `spotify-player` `cover_img_pixels` / `--features pixelate`; `i` toggle
- **Config** via `~/.config/music-cli/app.toml` (theme, player, queue, UI)
- **CLI scripting** — `music-cli search "query" --json | jq`

Inspired by `spotify-player`'s config hierarchy, playback bar, and visualization — replacing `rspotify`/`librespot` with `yt-dlp`/`ytmusicapi`/`mpv`.

## Demo

```
music-cli                          # launch TUI
music-cli search "lofi hip hop" --json | jq '.[0]'
music-cli search "stereo love" --limit 5 | cat
```

TUI layout: `Search Results | Queue` on top, `Cover + Playback (now playing + progress + viz 8 rows)` at bottom.

## Requirements

- **Python** 3.11+
- **System:** `mpv`, `yt-dlp`, `ffmpeg` (and `pipewire`/`pulseaudio` for audio)
- **Optional:** `Pillow` + `requests` (cover art), `numpy` (visualization FFT), Kitty terminal for native image protocol

Check:

```bash
python --version   # >=3.11
mpv --version
yt-dlp --version
ffmpeg -version
```

## Installation

### Arch Linux (Recommended)

`Music-CLI` is a Python app — install system deps from official repos, then the app via `pipx` (isolated, PEP 668-compliant).

**1. Install system dependencies:**

```bash
sudo pacman -Syu
sudo pacman -S mpv yt-dlp ffmpeg python-pipx
# optional but recommended for best experience:
sudo pacman -S pipewire pipewire-pulse pipewire-alsa  # audio
# Kitty for native cover art (otherwise half-block fallback is used):
sudo pacman -S kitty
```

> `yt-dlp` in `[extra]` and `mpv` in `[extra]` are kept current. If YouTube breaks, update: `sudo pacman -Syu yt-dlp` or `yt-dlp -U` (pipx install).

**2. Install Music-CLI:**

Option A — **pipx** (recommended, isolated venv, `music-cli` on `PATH`):

```bash
pipx install git+https://github.com/<your-org>/Music-CLI.git
# or from a local clone:
git clone https://github.com/<your-org>/Music-CLI.git
cd Music-CLI
pipx install -e .
```

Option B — **pip** with `--break-system-packages` (if you prefer system pip):

```bash
pip install --break-system-packages -e .
```

Option C — **venv** (manual):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

**3. Verify:**

```bash
music-cli --help
music-cli search "love me not" --limit 3 --json | jq
music-cli  # TUI: type a query, Enter to search, Enter again to play
```

**Update:**

```bash
pipx upgrade music-cli
# or
sudo pacman -Syu mpv yt-dlp   # keep extractors fresh
yt-dlp -U                     # if installed via pipx
```

**Uninstall:**

```bash
pipx uninstall music-cli
```

#### AUR (if you publish)

```bash
yay -S music-cli          # AUR helper
# or
paru -S music-cli
```

> AUR `PKGBUILD` should `depends=(mpv yt-dlp ffmpeg python python-textual python-ytmusicapi python-numpy python-pillow python-requests)` and install `music-cli` via `pip --root`.

### Other Distros

**Debian / Ubuntu / Pop!_OS:**

```bash
sudo apt update
sudo apt install mpv yt-dlp ffmpeg pipx
pipx install git+https://github.com/<your-org>/Music-CLI.git
```

**Fedora / RHEL:**

```bash
sudo dnf install mpv yt-dlp ffmpeg pipx
pipx install git+https://github.com/<your-org>/Music-CLI.git
```

**macOS (Homebrew):**

```bash
brew install mpv yt-dlp ffmpeg pipx
pipx install git+https://github.com/<your-org>/Music-CLI.git
```

**NixOS (`flake.nix`):**

```bash
nix run github:<your-org>/Music-CLI
# or add to environment.systemPackages
```

### Development Install

```bash
git clone https://github.com/<your-org>/Music-CLI.git
cd Music-CLI
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# or with pipx:
pipx install -e ".[dev]" --force
```

## Usage

**TUI (default):**

```bash
music-cli
```

Workflow: focus search input → type query → `Enter` (search) → `j/k` navigate → `Enter` play single + autoplay radio, `A` play all results as context, `z` add to queue.

**CLI:**

```bash
music-cli search "never gonna give you up" --json | jq '.[0]'
music-cli search "lofi" --limit 5 --json > results.json
music-cli --help
music-cli search --help
```

**Examples:**

```bash
# JSON scripting like spotify-player
music-cli search "daft punk" --json | jq -r '.[0].url' | xargs mpv --no-video
# Play first result via queue helper (future: `music-cli playback start`)
```

## Keybindings

| Key | Action | Notes |
|-----|--------|-------|
| `q`, `Ctrl+c` | Quit | |
| `?` | Toggle help | |
| `/` | Focus search | |
| `Enter` | Play selected (single + mix) | Inserts after current, prefetches radio |
| `A` (`Shift+a`) | Play context | Queue all search results |
| `Space` | Pause / resume | |
| `n` / `p` | Next / previous | Respects shuffle/repeat |
| `+` / `-` | Volume +5 / -5 | `volume` in `app.toml` |
| `<` / `>` (`,`/`.`) | Seek -5s / +5s | `seek_secs` in `app.toml` |
| `z` | Add to queue | Selected search result |
| `s` | Toggle shuffle | `off/on` |
| `r` | Toggle repeat | `off → all → one` |
| `c` | Clear queue | |
| `a` | Toggle autoplay | Radio when queue ends |
| `v` | Toggle visualization | 64 bars, 8 rows |
| `i` | Toggle cover | Kitty / half-blocks |
| `Ctrl+Right` / `Ctrl+Left` | Pixels + / - | `8..720`, like `cover_img_pixels` |
| `j` / `k`, `Up`/`Down`, `PgUp`/`PgDn` | Navigate | vim-style |

## Configuration

Config lives in `~/.config/music-cli/app.toml` (created from `config/app.toml` on first run). Override dir with `$MUSIC_CLI_CONFIG`.

```toml
[player]
volume = 70
seek_secs = 5
ytdl_format = "bestaudio/best"

[ui]
theme = "default"
page_size = 20
playback_window_position = "bottom"
enable_audio_visualization = true
show_cover = true
cover_size = 12          # cache square size (×12 px)
cover_pixels = 512       # 8..720 — 8=blocky pixelate, 512=sharp (like spotify-player pixelate)

[queue]
autoplay = true
mix_limit = 10           # radio tracks prefetched per seed
```

Cache (covers, etc.) in `~/.cache/music-cli` (`$MUSIC_CLI_CACHE`).

- **Visualization:** `enable_audio_visualization` mirrors `spotify-player`'s flag. Real FFT needs `parec` or `pw-record` (PipeWire) + `numpy`; otherwise smooth fake bars.
- **Cover:** `show_cover` + `cover_pixels` mirrors `cover_img_pixels`. Kitty terminal shows true image; others show 24×12 half-blocks.
- **Tips:** `cover_pixels=8` for retro 8×8 pixel art, `720` for max sharpness.

## How It Works

```
Search (ytmusicapi search filter=songs) ──┐
                                          ├─► Queue (dedup, channel diversity) ──► mpv --no-video (ytdl-hook) ──► Pulse/PipeWire
Radio  (ytmusicapi get_watch_playlist) ────┘         ▲                          (IPC /tmp/music-cli-*.sock)
                                                     │ auto-next on eof-reached/idle
Covers (ytmusicapi thumbnails → Pillow cache) ───────┘
Viz    (parec/pw-record → numpy rfft 64 log bands or smooth fake) ──► Textual TUI
```

- **Search/Radio:** `ytmusicapi` (`WEB_REMIX` client) for music-optimized ranking and mixes; `yt-dlp` `RD` playlist + `ytsearch` as fallbacks. Channel diversity (`max 2/channel`) and duration filtering (`60–600s`) remove compilations/long loops.
- **Playback:** `MpvPlayer` spawns `mpv --idle --input-ipc-server` and drives it via JSON IPC (`loadfile`, `seek`, `set_property volume`). Progress polled every 500ms; EOF detected via `eof-reached`/`idle-active`.
- **Why mpv?** Handles YouTube DASH (split audio) natively, unlike `ffplay`/`vlc --input-slave`. No download needed — true streaming.

## Troubleshooting

- **`mpv not found`:** `sudo pacman -S mpv && which mpv`
- **No audio / `Audio device` error (Arch):** `systemctl --user status pipewire pipewire-pulse` → `sudo pacman -S pipewire-pulse wireplumber && systemctl --user restart pipewire`
- **`yt-dlp` extractor fails / `403` / `nsig`:** `yt-dlp -U` or `sudo pacman -Syu yt-dlp`; YouTube changes signatures often
- **Cover shows `♪ no cover`:** Check `ping music.youtube.com`; thumbnails are fetched via `requests` and cached — delete `~/.cache/music-cli/covers` to retry
- **Visualization flat:** Install `numpy` (`pipx inject music-cli numpy`) and ensure `parec`/`pw-record` exist; fake bars still show if capture fails
- **Kitty image not showing:** Ensure `TERM=xterm-kitty` and `kitty` >=0.28; fallback half-blocks always work
- **Wayland clipboard / `O` open link (future):** `sudo pacman -S wl-clipboard`
- **PEP 668 `externally-managed-environment`:** Use `pipx` (recommended) or `pipx install -e . --break-system-packages` is not needed with `pipx`

Logs: `RUST_LOG` equivalent is `MUSIC_CLI_LOG=debug` (future) and `~/.cache/music-cli/*.log`.

## Roadmap

- [ ] Lyrics page (`lrclib` / YouTube captions) like `g L` in `spotify-player`
- [ ] MPRIS / `media-control` (Linux) + desktop notifications
- [ ] Daemon mode (`-d`) + socket CLI (`client_port` 8080)
- [ ] `browse` / `charts` / `moods` (`ytmusicapi get_mood_playlists` / `get_charts`)
- [ ] `fzf` fuzzy search, `player_event_hook`, themes (`theme.toml`)
- [ ] Publish to AUR, add `PKGBUILD` and `flake.nix`

## Acknowledgement

Built with [Textual](https://github.com/Textualize/textual), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [mpv](https://mpv.io), and inspired by [`aome510/spotify-player`](https://github.com/aome510/spotify-player) (ratatui, librespot, rspotify). Thanks to the authors of those projects.

## License

MIT — see [LICENSE](LICENSE)
