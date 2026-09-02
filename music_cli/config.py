from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def default_config_dir() -> Path:
    return Path(os.environ.get("MUSIC_CLI_CONFIG", Path.home() / ".config" / "music-cli"))


def default_cache_dir() -> Path:
    return Path(os.environ.get("MUSIC_CLI_CACHE", Path.home() / ".cache" / "music-cli"))


@dataclass
class PlayerConfig:
    volume: int = 70
    seek_secs: int = 5
    ytdl_format: str = "bestaudio/best"


@dataclass
class UIConfig:
    playback_window_position: str = "bottom"  # top|bottom
    theme: str = "default"
    page_size: int = 20
    enable_audio_visualization: bool = True
    show_cover: bool = True
    cover_size: int = 10


@dataclass
class QueueConfig:
    autoplay: bool = True
    mix_limit: int = 10


@dataclass
class AppConfig:
    player: PlayerConfig = field(default_factory=PlayerConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    queue: QueueConfig = field(default_factory=QueueConfig)
    client_port: int = 8080

    @classmethod
    def load(cls, config_dir: Path | None = None) -> AppConfig:
        cfg = cls()
        cdir = config_dir or default_config_dir()
        path = cdir / "app.toml"
        if path.exists():
            try:
                data = tomllib.loads(path.read_text())
                p = data.get("player", {})
                u = data.get("ui", {})
                if "volume" in p:
                    cfg.player.volume = int(p["volume"])
                if "seek_secs" in p:
                    cfg.player.seek_secs = int(p["seek_secs"])
                if "ytdl_format" in p:
                    cfg.player.ytdl_format = str(p["ytdl_format"])
                if "theme" in u:
                    cfg.ui.theme = str(u["theme"])
                if "page_size" in u:
                    cfg.ui.page_size = int(u["page_size"])
                if "enable_audio_visualization" in u:
                    cfg.ui.enable_audio_visualization = bool(u["enable_audio_visualization"])
                if "show_cover" in u:
                    cfg.ui.show_cover = bool(u["show_cover"])
                if "cover_size" in u:
                    cfg.ui.cover_size = int(u["cover_size"])
                q = data.get("queue", {})
                if "autoplay" in q:
                    cfg.queue.autoplay = bool(q["autoplay"])
                if "mix_limit" in q:
                    cfg.queue.mix_limit = int(q["mix_limit"])
            except Exception:
                pass
        return cfg
