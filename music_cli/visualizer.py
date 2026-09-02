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
        out = []
        for i in range(BARS):
            # Bass heavy on left, decay to right (like screenshot: tall left, low right)
            bass_decay = math.exp(-i / 22)  # sharp falloff
            # Two moving peaks like kick + snare
            peak1 = 0.55 * max(0, math.sin(t * 2.2 + i * 0.18 + self._phase)) ** 1.5
            peak2 = 0.35 * max(0, math.sin(t * 4.5 - i * 0.12 + 1.3)) ** 1.2
            noise = 0.12 * random.random()
            # add occasional tall spike at 18-22 (as in screenshot)
            spike = 0.0
            if 16 <= i <= 23:
                spike = 0.35 * max(0, math.sin(t * 0.9 + i) ) * (1 - abs(i - 19.5) / 4)
            v = bass_decay * 0.45 + peak1 * bass_decay + peak2 * 0.7 + noise * (0.4 if i > 40 else 1) + spike
            if i > 50:
                v *= 0.5
            out.append(min(1.0, max(0, v)))
        return out

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
            self.bars[i] += (self.targets[i] - self.bars[i]) * 0.5

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
