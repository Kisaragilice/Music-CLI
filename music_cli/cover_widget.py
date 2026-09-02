from __future__ import annotations

import os
import sys
from pathlib import Path

from textual.widgets import Static


class CoverWidget(Static):
    """Shows cover art: Kitty graphics try + colored half-blocks fallback (works everywhere)."""

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._path: Path | None = None
        self._enabled = True
        self._w_cells = 20
        self._h_cells = 10
        self._is_kitty = "kitty" in os.environ.get("TERM", "") or bool(os.environ.get("KITTY_WINDOW_ID"))

    def set_cover(self, path: Path | None):
        self._path = path if path and path.exists() else None
        self.update(self.render())

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.update(self.render())

    def _to_blocks(self, path: Path) -> str:
        try:
            from PIL import Image

            im = Image.open(path).convert("RGB")
            w, h = self._w_cells, self._h_cells * 2
            im = im.resize((w, h), Image.LANCZOS)
            lines = []
            for y in range(0, h, 2):
                line = ""
                for x in range(w):
                    r1, g1, b1 = im.getpixel((x, y))
                    r2, g2, b2 = im.getpixel((x, y + 1))
                    line += f"[rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})]▀[/]"
                lines.append(line)
            return "\n".join(lines)
        except Exception:
            return "♪ no cover"

    def render(self) -> str:
        if not self._enabled or not self._path or not self._path.exists():
            return "♪\nno\ncover"
        if self._is_kitty:
            try:
                import base64

                data = self._path.read_bytes()
                b64 = base64.b64encode(data).decode()
                esc = f"\x1b_Ga=T,f=100,c={self._w_cells},r={self._h_cells};{b64}\x1b\\"
                sys.stdout.write(esc)
                sys.stdout.flush()
                return self._to_blocks(self._path)
            except Exception:
                pass
        return self._to_blocks(self._path)
