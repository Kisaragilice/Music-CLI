from __future__ import annotations


def resolve_url(youtube_url: str, ytdl_format: str = "bestaudio/best") -> dict:
    """Resolve youtube url to direct info via yt-dlp. Returns info dict with url."""
    import yt_dlp

    ydl_opts = {"quiet": True, "no_warnings": True, "format": ytdl_format}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info or {}
