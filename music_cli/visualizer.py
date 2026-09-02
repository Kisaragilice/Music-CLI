from __future__ import annotations

import math
import random
import time

from textual.widgets import Static

try:
    import numpy as np

    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

# 64 log-scale bands like spotify-player (bass left -> treble right)
BARS = 64
HEIGHT = 8
BLOCKS = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
COLORS_LOW = "#1DB954"  # spotify green for bass
COLORS_HIGH = "#1E90FF"  # blue for treble


class AudioVisualizer(Static):
    """Real-time bar chart: 64 log-scale bands. Uses audio capture if available, else animated fake."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self.bars = [0.0] * BARS
        self.targets = [0.0] * BARS
        self.enabled = True
        self.playing = False
        # log scale weights: bass more energy
        self._log_scale = [math.log1p(i) / math.log1p(BARS) for i in range(BARS)]
        self._phase = random.random() * 10
        self._pcm_proc = None
        self._pcm_buf = bytearray()
        self._try_start_capture()

    def _try_start_capture(self):
        """Try to capture system monitor via parec/pw-record. Non-fatal."""
        if not HAS_NUMPY:
            return
        import shutil
        import subprocess

        # Prefer pw-record (pipewire) then parec
        cmd = None
        if shutil.which("pw-record"):
            # find default monitor: pw-record --help shows monitor?
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
            # read ~2048 frames * 4 bytes (s16 stereo)
            chunk = self._pcm_proc.stdout.read(8192)
            if not chunk or len(chunk) < 4096:
                return None
            arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            # stereo -> mono
            if len(arr) % 2 == 0:
                arr = (arr[0::2] + arr[1::2]) / 2
            # window + rfft
            window = np.hanning(len(arr))
            spectrum = np.abs(np.fft.rfft(arr * window))
            # map to 64 log bands
            n = len(spectrum)
            out = []
            for i in range(BARS):
                # log spaced indices
                start = int((math.pow(2, i / 10) - 1) / (math.pow(2, BARS / 10) - 1) * (n - 1))
                end = int((math.pow(2, (i + 1) / 10) - 1) / (math.pow(2, BARS / 10) - 1) * (n - 1))
                end = max(start + 1, end)
                band = float(np.mean(spectrum[start:end]))
                # normalize roughly 0-1 (heuristic)
                band = min(1.0, band * 8)
                out.append(band)
            return out
        except Exception:
            return None

    def _fake_bars(self, t: float) -> list[float]:
        # Animated fake: bass stronger, mid wandering, high sparse
        out = []
        for i in range(BARS):
            # bass boost left
            bass = (1 - i / BARS) * 0.6
            # wave
            w1 = 0.3 * abs(math.sin(t * 1.7 + i * 0.15 + self._phase))
            w2 = 0.25 * abs(math.sin(t * 3.1 - i * 0.08))
            w3 = 0.15 * random.random() * (0.3 if i > 40 else 1.0)  # treble quieter
            v = bass * 0.5 + w1 + w2 + w3
            # high freq falloff
            if i > 48:
                v *= 0.6
            out.append(min(1.0, v))
        return out

    def update_state(self, playing: bool, enabled: bool):
        self.playing = playing
        self.enabled = enabled

    def render_bars(self) -> str:
        if not self.enabled or not self.playing:
            # flat line when paused/hidden
            return " " * BARS

        # try real FFT first
        real = self._read_pcm_and_fft() if self.playing else None
        if real:
            self.targets = real
        else:
            self.targets = self._fake_bars(time.time())

        # smooth
        for i in range(BARS):
            self.bars[i] += (self.targets[i] - self.bars[i]) * 0.45

        # build row string with height mapping + rich markup for colors
        # Use block chars scaled to 0-8
        chars = []
        for v in self.bars:
            idx = int(v * (len(BLOCKS) - 1))
            chars.append(BLOCKS[idx])

        # Apply gradient via markup per segment ( textual supports markup )
        # For performance, return plain string; color via widget styles
        return "".join(chars)

    def on_mount(self):
        self.set_interval(0.06, self._tick)  # ~16 fps

    def _tick(self):
        if not self.enabled:
            return
        # trigger repaint
        self.update(self.render_bars())

    def on_unmount(self):
        try:
            if self._pcm_proc:
                self._pcm_proc.terminate()
        except Exception:
            pass
