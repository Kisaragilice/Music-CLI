from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class Track:
    id: str
    title: str
    channel: str | None = None
    duration: int | None = None  # seconds
    url: str = ""  # youtube url
    thumbnail: str | None = None


def _fmt_duration(secs: int | None) -> str:
    if not secs:
        return "-"
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def search_ytdlp(query: str, limit: int = 10) -> list[Track]:
    """Search YouTube using yt-dlp ytsearch (no API key)."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": f"ytsearch{limit}",
    }
    # yt-dlp search string
    search_str = f"ytsearch{limit}:{query}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_str, download=False)
        entries = info.get("entries", []) if info else []
        tracks: list[Track] = []
        for e in entries:
            if not e:
                continue
            vid = e.get("id", "")
            title = e.get("title", vid)
            channel = e.get("uploader") or e.get("channel") or e.get("uploader_id")
            duration = e.get("duration")
            thumb = None
            thumbs = e.get("thumbnails")
            if thumbs:
                thumb = thumbs[-1].get("url")
            url = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
            # for flat extract, url may be just id
            if vid and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={vid}"
            tracks.append(Track(id=vid, title=title, channel=channel, duration=duration, url=url, thumbnail=thumb))
        return tracks


def _entries_to_tracks(entries, exclude_ids: set[str] | None = None) -> list[Track]:
    tracks: list[Track] = []
    for e in entries or []:
        if not e:
            continue
        vid = e.get("id", "")
        if exclude_ids and vid in exclude_ids:
            continue
        title = e.get("title", vid)
        channel = e.get("uploader") or e.get("channel") or e.get("uploader_id")
        duration = e.get("duration")
        thumb = None
        thumbs = e.get("thumbnails")
        if thumbs:
            thumb = thumbs[-1].get("url")
        url = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
        if vid and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={vid}"
        tracks.append(Track(id=vid, title=title, channel=channel, duration=duration, url=url, thumbnail=thumb))
    return tracks


def get_mix_tracks(track: Track, limit: int = 10, exclude_ids: set[str] | None = None) -> list[Track]:
    """YT Music radio first, then RD mix, then ytsearch fallback."""
    # Try YT Music radio (best quality)
    try:
        from .ytmusic import get_radio_tracks

        res = get_radio_tracks(track, limit=limit, exclude_ids=exclude_ids)
        if len(res) >= 3:
            return res
    except Exception:
        pass

    exclude = set(exclude_ids or set())
    exclude.add(track.id)

    # Try RD mix playlist
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    mix_url = f"https://www.youtube.com/watch?v={track.id}&list=RD{track.id}"
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(mix_url, download=False)
            entries = info.get("entries") if info else None
            if entries:
                tracks = _entries_to_tracks(entries, exclude)
                tracks = [t for t in tracks if t.id != track.id]
                if len(tracks) >= 3:
                    return tracks[:limit]
    except Exception:
        pass

    # Fallback: ytsearch mix
    query = f"{track.title} {track.channel or ''} mix".strip()
    try:
        tracks = search_ytdlp(query, limit=limit + 5)
        tracks = [t for t in tracks if t.id not in exclude]
        return tracks[:limit]
    except Exception:
        return []


def search_music_ytdlp_fallback(query: str, limit: int = 10) -> list[Track]:
    return search_ytdlp(query, limit)


# CLI helper: print json
def search_json(query: str, limit: int = 10) -> str:
    # try YT Music first
    try:
        from .ytmusic import search_music

        tracks = search_music(query, limit=limit)
        if tracks:
            data = [{"id": t.id, "title": t.title, "channel": t.channel, "duration": t.duration, "url": t.url} for t in tracks]
            return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        pass
    tracks = search_ytdlp(query, limit)
    data = [
        {"id": t.id, "title": t.title, "channel": t.channel, "duration": t.duration, "url": t.url}
        for t in tracks
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)
