from __future__ import annotations

import argparse
import json
import sys

from .search import search_json
from .config import AppConfig


def main():
    parser = argparse.ArgumentParser(prog="music-cli", description="CLI streaming music via yt-dlp + mpv")
    sub = parser.add_subparsers(dest="cmd")

    p_search = sub.add_parser("search", help="Search YouTube")
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.cmd == "search":
        q = " ".join(args.query)
        # ensure yt-dlp installed
        try:
            out = search_json(q, limit=args.limit)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(out)
        else:
            data = json.loads(out)
            for i, t in enumerate(data, 1):
                dur = t.get("duration")
                dur_s = f"{dur//60}:{dur%60:02d}" if isinstance(dur, int) else "-"
                print(f"{i:2}. {t['title'][:60]:60}  {t.get('channel','-')[:20]:20}  {dur_s:6}  {t['url']}")
        return

    # default: launch TUI
    # check deps
    import shutil
    if shutil.which("mpv") is None:
        print("mpv not found. Install mpv (sudo pacman -S mpv / sudo apt install mpv)", file=sys.stderr)
        sys.exit(1)
    try:
        import textual  # noqa
    except ImportError:
        print("textual not installed. Run: pip install -e .", file=sys.stderr)
        sys.exit(1)

    from .app import run
    run()
