# Music-CLI

CLI streaming music player tanpa GUI — `yt-dlp` + `mpv`, terinspirasi `spotify-player` (`aome510/spotify-player`).

## Fitur (MVP)
- Search YouTube via `yt-dlp ytsearch` (tanpa API key)
- Streaming audio-only via `mpv --no-video --ytdl-format=bestaudio`
- TUI `Textual`: search input, hasil tabel, queue, playback bar + progress
- Kontrol vim-like: `j/k`, `enter` play, `space` pause, `n/p` next/prev, `+/-` volume, `</>` seek, `q` quit, `?` help
- Queue (Z add, auto-next, shuffle/repeat)
- Config `~/.config/music-cli/app.toml`

## Requirements
- Python 3.11+
- `mpv`, `yt-dlp`, `ffmpeg`

```bash
sudo pacman -S mpv yt-dlp ffmpeg    # arch
sudo apt install mpv yt-dlp ffmpeg  # debian
```

## Install
```bash
pipx install -e .
# atau
pip install -e .
```

## Usage
```bash
music-cli                    # TUI
music-cli search "lofi hip hop" --json | jq
music-cli --help
```

## Config
`~/.config/music-cli/app.toml` (copy dari `config/app.toml`)
