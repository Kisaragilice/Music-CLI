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
HEIGHT = 6  # rows tall like spotify-player screenshot
# Color gradient bass green -> cyan -> blue
GRAD = [
    "#12c46b",
    "#18c77a",
    "#1fd089",
    "#2ad4b0",
    "#2ac4d6",
    "#2aa8e6",
    "#2a8de6",
    "#2a6de6",
]


def _interp_color(i: int) -> str:
    # map bar index 0..63 to gradient
    idx = int(i / BARS * (len(GRAD) - 1))
    return GRAD[idx]


class AudioVisualizer(Static):
    """64 log-scale bars, multi-row colored, like spotify-player."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.bars = [0.0] * BARS
        self.targets = [0.0] * BARS
        self.enabled = True
        self.playing = False
        self._phase = random.random() * 10
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

            # non-blocking peek
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
                # log spaced: more resolution at low freq
                f0 = math.pow(10, i / BARS * 3)  # 1..1000
                f1 = math.pow(10, (i + 1) / BARS * 3)
                s = int(f0 / 1000 * n)
                e = int(f1 / 1000 * n)
                s = max(0, min(n - 1, s))
                e = max(s + 1, min(n, e))
                band = float(np.mean(spectrum[s:e]))
                band = min(1.0, band * 10 * (1.2 - i / BARS * 0.5))
                out.append(band)
            return out
        except Exception:
            return None

    def _fake_bars(self, t: float) -> list[float]:
        # Smooth, regular spectrum like spotify-player screenshot:
        # envelope decays smoothly from bass to treble, animated with slow beats, no high-frequency noise.
        # Use deterministic smooth waves only (no random) + light smoothing across neighboring bars.
        raw = []
        beat = 0.5 + 0.5 * math.sin(t * 1.4 + self._phase)  # slow pump 0..1
        beat2 = 0.5 + 0.5 * math.sin(t * 2.8 + 1.1)
        for i in range(BARS):
            env = math.exp(-i / 32) * 0.32
            bump = 0.06 * math.exp(-((i - 18) / 9) ** 2)
            base = env + bump
            mod = 0.18 * math.sin(t * 1.0 + i * 0.10 + self._phase) * (1 - i / BARS * 0.5)
            mod = max(0, mod)
            pump = beat * 0.08 * math.exp(-i / 16)
            v = base * (0.75 + mod) + pump
            # treble quiet
            if i > 48:
                v *= 0.55
            elif i > 36:
                v *= 0.78
            raw.append(min(1.0, v))
        smooth = []
        for i in range(BARS):
            a = raw[max(0, i - 1)]
            b = raw[i]
            c = raw[min(BARS - 1, i + 1)]
            smooth.append((a * 0.25 + b * 0.5 + c * 0.25) * 0.78)
        return smooth

    def update_state(self, playing: bool, enabled: bool):
        self.playing = playing
        self.enabled = enabled
        if not enabled or not playing:
            self.bars = [0.0] * BARS

    def render(self) -> Text:
        if not self.enabled or not self.playing:
            # return empty with height to keep layout but transparent
            return Text("\n" * (HEIGHT - 1), no_wrap=True)

        real = self._read_pcm_and_fft()
        if real and any(v > 0.02 for v in real):
            self.targets = real
        else:
            self.targets = self._fake_bars(time.time())

        for i in range(BARS):
            self.bars[i] += (self.targets[i] - self.bars[i]) * 0.35

        # Build HEIGHT rows top->bottom with solid blocks
        rows: list[Text] = [Text(no_wrap=True) for _ in range(HEIGHT)]
        for i, v in enumerate(self.bars):
            h = int(v * HEIGHT + 0.5)  # 0..HEIGHT
            col = _interp_color(i)
            for r in range(HEIGHT):
                # r=0 top, r=HEIGHT-1 bottom
                filled = (HEIGHT - r) <= h
                ch = "█" if filled else " "
                # bass glows brighter at bottom: add style
                style = col if filled else ""
                rows[r].append(ch, style=style)
        txt = Text(no_wrap=True)
        for r, row in enumerate(rows):
            txt.append_text(row)
            if r < HEIGHT - 1:
                txt.append("\n")
        return txt

    def on_mount(self):
        self.set_interval(0.05, self._tick)  # 20 fps

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
