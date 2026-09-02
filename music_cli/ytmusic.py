from __future__ import annotations

import re
from typing import Optional

from .search import Track

_BLACKLIST_RE = re.compile(r"(\d+\s*hours?|nonstop|compilation|loop|\b10\s*h\b)", re.I)


def _clean_title(t: str) -> str:
    # remove brackets noise but keep core
    return t.strip()


def _yt_to_track(item: dict, video_id_key="videoId") -> Optional[Track]:
    vid = item.get("videoId") or item.get(video_id_key)
    if not vid:
        return None
    title = item.get("title") or vid
    # artists is list of dicts
    arts = item.get("artists") or []
    channel = None
    if arts and isinstance(arts, list):
        channel = ", ".join(a.get("name", "") for a in arts if a.get("name"))
    if not channel:
        channel = item.get("author") or item.get("artist")
    dur = item.get("duration_seconds") or item.get("duration") or item.get("lengthSeconds") or item.get("length") or item.get("lengthText")
    # lengthText may be dict
    if isinstance(dur, dict):
        # e.g. {"runs":[{"text":"3:22"}]} or {"simpleText":"3:22"}
        if "simpleText" in dur:
            dur = dur["simpleText"]
        elif "runs" in dur and dur["runs"]:
            dur = dur["runs"][0].get("text", "")
    if isinstance(dur, str) and dur.isdigit():
        dur = int(dur)
    # sometimes duration is "3:45"
    if isinstance(dur, str) and ":" in dur:
        try:
            parts = list(map(int, dur.split(":")))
            if len(parts) == 2:
                dur = parts[0] * 60 + parts[1]
            elif len(parts) == 3:
                dur = parts[0] * 3600 + parts[1] * 60 + parts[2]
        except Exception:
            dur = None
    thumb = None
    thumbs = item.get("thumbnails") or item.get("thumbnail")
    if isinstance(thumbs, list) and thumbs:
        thumb = thumbs[-1].get("url")
    elif isinstance(thumbs, dict):
        thumb = thumbs.get("url")
    url = f"https://music.youtube.com/watch?v={vid}"
    return Track(id=vid, title=_clean_title(title), channel=channel, duration=dur if isinstance(dur, int) else None, url=url, thumbnail=thumb)


def _get_ytm() -> object:
    from ytmusicapi import YTMusic

    # unauthenticated is fine; try oauth.json if exists
    try:
        from pathlib import Path

        p = Path.home() / ".cache" / "music-cli" / "oauth.json"
        if p.exists():
            return YTMusic(str(p))
    except Exception:
        pass
    return YTMusic()


def search_music(query: str, limit: int = 20) -> list[Track]:
    ytm = _get_ytm()
    try:
        res = ytm.search(query, filter="songs", limit=limit)  # type: ignore
    except Exception:
        return []
    tracks: list[Track] = []
    for item in res or []:
        t = _yt_to_track(item)
        if t:
            tracks.append(t)
    return tracks[:limit]


def get_radio_tracks(seed: Track, limit: int = 25, exclude_ids: set[str] | None = None, min_dur=60, max_dur=600, max_per_channel=2) -> list[Track]:
    exclude = set(exclude_ids or set())
    exclude.add(seed.id)
    ytm = _get_ytm()
    raw_tracks = []
    try:
        data = ytm.get_watch_playlist(videoId=seed.id, limit=limit + 10, radio=True)  # type: ignore
        raw_tracks = data.get("tracks", []) if isinstance(data, dict) else []
    except Exception:
        raw_tracks = []

    tracks: list[Track] = []
    channel_counts: dict[str, int] = {}
    for item in raw_tracks:
        t = _yt_to_track(item)
        if not t or t.id in exclude:
            continue
        # filters
        if t.duration is not None and not (min_dur <= t.duration <= max_dur):
            continue
        if _BLACKLIST_RE.search(t.title):
            continue
        # channel diversity
        ch = (t.channel or "").lower()
        if ch:
            cnt = channel_counts.get(ch, 0)
            if cnt >= max_per_channel:
                continue
            channel_counts[ch] = cnt + 1
        tracks.append(t)
        exclude.add(t.id)
        if len(tracks) >= limit:
            break

    # if not enough, try continuation via playlistId RDAMVM
    if len(tracks) < limit * 0.5:
        try:
            # get_watch_playlist returns playlistId like RDAMVM...
            pid = None
            if isinstance(data, dict):
                pid = data.get("playlistId")
            if pid:
                more = ytm.get_playlist(pid, limit=limit)  # type: ignore
                for item in (more.get("tracks", []) if isinstance(more, dict) else []):
                    t = _yt_to_track(item)
                    if not t or t.id in exclude:
                        continue
                    if t.duration is not None and not (min_dur <= t.duration <= max_dur):
                        continue
                    if _BLACKLIST_RE.search(t.title):
                        continue
                    ch = (t.channel or "").lower()
                    if ch and channel_counts.get(ch, 0) >= max_per_channel:
                        continue
                    if ch:
                        channel_counts[ch] = channel_counts.get(ch, 0) + 1
                    tracks.append(t)
                    exclude.add(t.id)
                    if len(tracks) >= limit:
                        break
        except Exception:
            pass
    return tracks[:limit]
