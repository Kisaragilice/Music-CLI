from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class MpvPlayer:
    """Thin wrapper around mpv --input-ipc-server. Handles audio-only streaming (ytdl_hook)."""

    def __init__(self, ytdl_format: str = "bestaudio/best", volume: int = 70):
        self.ytdl_format = ytdl_format
        self.volume = volume
        self._proc: subprocess.Popen | None = None
        self._socket_path: Path | None = None

    def _ensure_socket_path(self) -> Path:
        if self._socket_path and self._socket_path.exists():
            return self._socket_path
        # use temp file
        tmp = tempfile.NamedTemporaryFile(prefix="music-cli-", suffix=".sock", delete=False)
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        self._socket_path = Path(tmp.name)
        return self._socket_path

    def start(self):
        if self._proc and self._proc.poll() is None:
            return
        sock = self._ensure_socket_path()
        cmd = [
            "mpv",
            "--no-video",
            "--idle=yes",
            f"--ytdl-format={self.ytdl_format}",
            f"--input-ipc-server={str(sock)}",
            f"--volume={self.volume}",
            "--no-terminal",
        ]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # wait for socket
        for _ in range(30):
            if sock.exists():
                break
            time.sleep(0.1)

    def _send(self, command: list) -> dict | None:
        if not self._socket_path or not self._socket_path.exists():
            return None
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(str(self._socket_path))
            s.sendall((json.dumps({"command": command}) + "\n").encode())
            data = s.recv(8192)
            s.close()
            if data:
                return json.loads(data.decode().strip().split("\n")[0])
        except Exception:
            return None
        return None

    def play(self, url: str):
        self.start()
        self._send(["loadfile", url, "replace"])

    def queue(self, url: str):
        self.start()
        self._send(["loadfile", url, "append-play"])

    def pause_toggle(self):
        self._send(["cycle", "pause"])

    def pause(self, do_pause: bool = True):
        self._send(["set_property", "pause", do_pause])

    def stop(self):
        self._send(["stop"])

    def next(self):
        self._send(["playlist-next"])

    def prev(self):
        self._send(["playlist-prev"])

    def set_volume(self, vol: int):
        vol = max(0, min(150, vol))
        self.volume = vol
        self._send(["set_property", "volume", vol])

    def seek(self, secs: float, relative: bool = True):
        mode = "relative" if relative else "absolute"
        self._send(["seek", secs, mode])

    def get_property(self, name: str):
        resp = self._send(["get_property", name])
        if resp and resp.get("error") == "success":
            return resp.get("data")
        return None

    def is_paused(self) -> bool | None:
        return self.get_property("pause")

    def get_time_pos(self) -> float | None:
        v = self.get_property("time-pos")
        return float(v) if v is not None else None

    def get_duration(self) -> float | None:
        v = self.get_property("duration")
        return float(v) if v is not None else None

    def terminate(self):
        try:
            if self._proc and self._proc.poll() is None:
                self._send(["quit"])
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
        finally:
            if self._socket_path and self._socket_path.exists():
                try:
                    self._socket_path.unlink()
                except Exception:
                    pass
            self._proc = None
