from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

import requests
from PIL import Image

from .config import default_cache_dir


def cache_path_for(url: str) -> Path:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return default_cache_dir() / "covers" / f"{h}.jpg"


def fetch_cover(url: str | None, size: int = 128) -> Path | None:
    if not url:
        return None
    try:
        p = cache_path_for(url)
        if p.exists() and p.stat().st_size > 0:
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=8, headers={"User-Agent": "music-cli/1.0"})
        r.raise_for_status()
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        # resize to square via PIL
        try:
            im = Image.open(tmp)
            im = im.convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            # square pad
            bg = Image.new("RGB", (size, size), (30, 30, 30))
            x = (size - im.width) // 2
            y = (size - im.height) // 2
            bg.paste(im, (x, y))
            bg.save(p, "JPEG", quality=85)
            tmp.unlink(missing_ok=True)
        except Exception:
            tmp.rename(p)
        return p
    except Exception:
        return None


def fetch_cover_async(url: str | None, cb, size: int = 128):
    def _run():
        p = fetch_cover(url, size)
        cb(p)

    threading.Thread(target=_run, daemon=True).start()
