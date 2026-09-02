from __future__ import annotations

import math
import random
import time

from rich.text import Text
from textual.widgets import Static

try:
    import numpy as np

    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

BARS = 64
HEIGHT = 8  # match spotify-player screenshot (taller)
GRAD = [
    "#1DB954",  # spotify green bass
    "#1ED760",
    "#2BC4A0",
    "#33B5C8",
    "#3AA0D6",
    "#3D8BDF",
    "#3A6FE3",
    "#2E5CE6",  # blue treble
]


def _interp_color(i: int) -> str:
    idx = int(i / BARS * (len(GRAD) - 1))
    return GRAD[idx]


class AudioVisualizer(Static):
    """64 log-scale bars bottom-up, like spotify-player screenshot."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.bars = [0.0] * BARS
        self.targets = [0.0] * BARS
        self.enabled = True
        self.playing = False
        self._phase = random.random() * 6
        self._pcm_proc = None
        self._try_start_capture()

    def _try_start_capture(self):
        if not HAS_NUMPY:
            return
        import shutil
        import subprocess

        cmd = None
        if shutil.which("pw-record"):
            cmd = ["pw-record", "--format=s16", "--rate=44100", "--channels=2", "-"]
        elif shutil.which("parec"):
            cmd = ["parec", "--raw", "--format=s16le", "--rate=44100", "--channels=2", "--monitor-stream", "--latency-msec=50"]
        if not cmd:
            return
        try:
            self._pcm_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except Exception:
            self._pcm_proc = None

    def _read_pcm_and_fft(self) -> list[float] | None:
        if not self._pcm_proc or not self._pcm_proc.stdout or not HAS_NUMPY:
            return None
        try:
            import select

            ready, _, _ = select.select([self._pcm_proc.stdout], [], [], 0)
            if not ready:
                return None
            chunk = self._pcm_proc.stdout.read(8192)
            if not chunk or len(chunk) < 4096:
                return None
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            if len(arr) % 2 == 0:
                arr = (arr[0::2] + arr[1::2]) / 2
            window = np.hanning(len(arr))
            spectrum = np.abs(np.fft.rfft(arr * window))
            n = len(spectrum)
            out: list[float] = []
            for i in range(BARS):
                f0 = math.pow(10, i / BARS * 3)
                f1 = math.pow(10, (i + 1) / BARS * 3)
                s = int(f0 / 1000 * n)
                e = int(f1 / 1000 * n)
                s = max(0, min(n - 1, s))
                e = max(s + 1, min(n, e))
                band = float(np.mean(spectrum[s:e]))
                band = min(1.0, band * 10 * (1.25 - i / BARS * 0.6))
                out.append(band)
            return out
        except Exception:
            return None

    def _fake_bars(self, t: float) -> list[float]:
        # Recreate screenshot shape: bass tall (green), peak at ~19-21 (brown highlight), slope down to treble low (blue)
        # Screenshot timeline 0:31/3:39 stable, not chaotic
        raw: list[float] = []
        # very slow breath to vary height slightly, not jitter
        breath = 0.5 + 0.5 * math.sin(t * 0.45 + self._phase)
        # second harmonic for gentle motion
        sway = 0.5 + 0.5 * math.sin(t * 0.78 + 1.2)
        for i in range(BARS):
            # log envelope: high bass, fast decay
            env = math.exp(-i / 26) * 0.52
            peak = 0.28 * math.exp(-((i - 20) / 3.5) ** 2)
            # secondary smaller bumps at 6-8 and 32
            bump2 = 0.08 * math.exp(-((i - 7) / 5) ** 2)
            bump3 = 0.05 * math.exp(-((i - 34) / 7) ** 2)
            base = env + peak + bump2 + bump3
            # slow sway scales bass/mid, not treble
            mod = (0.10 * math.sin(t * 0.35 + i * 0.06) + 0.06 * math.sin(t * 0.85 - i * 0.04))
            mod = max(-0.08, mod)
            pump = breath * 0.06 * math.exp(-i / 22)
            pump2 = sway * 0.04 * math.exp(-((i - 20) / 12) ** 2)  # peak breathes
            v = base * (0.92 + mod) + pump + pump2
            if i > 52:
                v *= 0.45
            elif i > 42:
                v *= 0.68
            elif i > 30:
                v *= 0.85
            raw.append(min(0.98, v))
        # 5-point smoothing for regularity (no random)
        smooth: list[float] = []
        for i in range(BARS):
            vals = [raw[max(0, min(BARS - 1, i + d))] for d in (-2, -1, 0, 1, 2)]
            s = vals[0] * 0.08 + vals[1] * 0.18 + vals[2] * 0.48 + vals[3] * 0.18 + vals[4] * 0.08
            smooth.append(s)
        return smooth

    def update_state(self, playing: bool, enabled: bool):
        self.playing = playing
        self.enabled = enabled
        if not enabled or not playing:
            self.bars = [0.0] * BARS

    def render(self) -> Text:
        if not self.enabled or not self.playing:
            return Text("\n" * (HEIGHT - 1), no_wrap=True)
        real = self._read_pcm_and_fft()
        if real and any(v > 0.02 for v in real):
            self.targets = real
        else:
            self.targets = self._fake_bars(time.time())
        for i in range(BARS):
            self.bars[i] += (self.targets[i] - self.bars[i]) * 0.22
        rows: list[Text] = [Text(no_wrap=True) for _ in range(HEIGHT)]
        for i, v in enumerate(self.bars):
            h = int(v * HEIGHT + 0.5)
            col = _interp_color(i)
            # dim treble slightly
            if i > 45 and h > 0:
                h = max(1, h - 1)
            for r in range(HEIGHT):
                filled = (HEIGHT - r) <= h
                ch = "█" if filled else " "
                style = col if filled else ""
                rows[r].append(ch, style=style)
        txt = Text(no_wrap=True)
        for r, row in enumerate(rows):
            txt.append_text(row)
            if r < HEIGHT - 1:
                txt.append("\n")
        return txt

    def on_mount(self):
        self.set_interval(0.06, self._tick)

    def _tick(self):
        if not self.enabled:
            return
        self.update(self.render())

    def on_unmount(self):
        try:
            if self._pcm_proc:
                self._pcm_proc.terminate()
        except Exception:
            pass
