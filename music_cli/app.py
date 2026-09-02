from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Label, ProgressBar, Static

from .config import AppConfig
from .player import MpvPlayer
from .queue import Queue
from .search import Track, _fmt_duration, get_mix_tracks


HELP_TEXT = """\
[q] quit  [?] help  [enter] play(single+mix)  [A] play context  [space] pause  [n] next  [p] prev
[+/-] vol  [</>] seek 5s  [z] queue  [s] shuffle  [r] repeat  [c] clear  [a] autoplay toggle
[/] focus search  [j/k] nav
"""


class MusicApp(App):
    CSS = """
    #search_input { height: 3; }
    #results { height: 1fr; }
    #queue { height: 1fr; }
    #playback { height: 5; border: solid $primary; padding: 0 1; }
    #help { height: 3; color: $text-muted; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "toggle_help", "Help"),
        Binding("space", "pause", "Pause"),
        Binding("n", "next", "Next"),
        Binding("p", "prev", "Prev"),
        Binding("plus,equals", "vol_up", "Vol+"),
        Binding("minus,underscore", "vol_down", "Vol-"),
        Binding("greater_than,period", "seek_forward", "Seek+"),
        Binding("less_than,comma", "seek_back", "Seek-"),
        Binding("z", "add_to_queue", "Add queue"),
        Binding("s", "toggle_shuffle", "Shuffle"),
        Binding("r", "toggle_repeat", "Repeat"),
        Binding("c", "clear_queue", "Clear"),
        Binding("slash", "focus_search", "Search"),
        Binding("a", "toggle_autoplay", "Autoplay"),
        Binding("A", "play_context", "Play context"),
    ]

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self.config = config or AppConfig.load()
        self.player = MpvPlayer(ytdl_format=self.config.player.ytdl_format, volume=self.config.player.volume)
        self.queue = Queue()
        self.search_results: list[Track] = []
        self.show_help = False
        self._was_playing = False
        self._eof_handled = False
        self._autoplay_fetching = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(placeholder="Search YouTube (enter to search) — e.g. lofi hip hop", id="search_input")
        with Horizontal():
            with Vertical(id="left"):
                yield Label("Search Results (enter=play, z=queue)", id="results_label")
                yield DataTable(id="results")
            with Vertical(id="right"):
                yield Label("Queue", id="queue_label")
                yield DataTable(id="queue")
        with Horizontal(id="playback"):
            yield Label("Stopped", id="now_playing")
            yield ProgressBar(id="progress", total=100, show_eta=False)
            yield Label("vol 70% | shuffle off | repeat off", id="status")
        yield Static(HELP_TEXT, id="help")
        yield Footer()

    def on_mount(self):
        for tid, t in [("results", ["#", "Title", "Channel", "Dur"]), ("queue", ["#", "Title", "Channel", "Dur"])]:
            dt: DataTable = self.query_one(f"#{tid}", DataTable)
            for col in t:
                dt.add_column(col, width=None if col != "Title" else None)
            dt.cursor_type = "row"
            dt.zebra_stripes = True
        self.query_one("#search_input", Input).focus()
        self.set_interval(0.5, self._poll_player)
        self.player.start()

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "search_input":
            return
        query = event.value.strip()
        if not query:
            return
        event.input.add_class("loading")
        try:
            # YT Music search first, fallback to yt-dlp
            def _search(q, lim):
                try:
                    from .ytmusic import search_music

                    r = search_music(q, limit=lim)
                    if r:
                        return r
                except Exception:
                    pass
                from .search import search_ytdlp

                return search_ytdlp(q, limit=lim)

            tracks = await asyncio.to_thread(_search, query, self.config.ui.page_size)
        except Exception as e:
            self.notify(f"Search error: {e}", severity="error")
            return
        finally:
            event.input.remove_class("loading")
        self.search_results = tracks
        dt: DataTable = self.query_one("#results", DataTable)
        dt.clear()
        for i, t in enumerate(tracks):
            dt.add_row(str(i + 1), t.title[:60], (t.channel or "-")[:20], _fmt_duration(t.duration))
        if tracks:
            dt.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        # Determine which table
        if event.data_table.id == "results":
            idx = event.cursor_row
            if 0 <= idx < len(self.search_results):
                self._play_index(idx, from_queue=False)
        elif event.data_table.id == "queue":
            idx = event.cursor_row
            if 0 <= idx < len(self.queue.items):
                self.queue.set_current(idx)
                self._play_current()

    def _play_index(self, idx: int, from_queue: bool):
        if from_queue:
            self.queue.set_current(idx)
            self._play_current()
            return
        track = self.search_results[idx]
        # single-mode: put selected track as current, insert after current
        if not self.queue.items:
            self.queue.add(track)
            self.queue.set_current(0)
        else:
            self.queue.add_next(track)
            self.queue.set_current(self.queue.current + 1 if self.queue.current >= 0 else len(self.queue.items) - 1)
        self._refresh_queue_table()
        self._play_current()
        # prefetch mix in background for autoplay diversity
        if self.config.queue.autoplay:
            self._prefetch_mix(track)

    def _prefetch_mix(self, seed: Track):
        if self._autoplay_fetching:
            return
        self._autoplay_fetching = True

        async def _fetch():
            try:
                exclude = {t.id for t in self.queue.items}
                tracks = await asyncio.to_thread(get_mix_tracks, seed, self.config.queue.mix_limit, exclude)
                if tracks:
                    self.queue.extend(tracks)
                    self._refresh_queue_table()
            finally:
                self._autoplay_fetching = False

        asyncio.create_task(_fetch())

    def _play_context(self):
        """Play all search results as context (old behavior)."""
        if not self.search_results:
            return
        self.queue.clear()
        for t in self.search_results:
            self.queue.add(t)
        self.queue.set_current(0)
        self._refresh_queue_table()
        self._play_current()

    def _play_current(self):
        track = self.queue.current_track()
        if not track:
            return
        self.query_one("#now_playing", Label).update(f"▶ {track.title} — {track.channel or ''}")
        self._was_playing = True
        self._eof_handled = False
        try:
            self.player.play(track.url)
        except Exception as e:
            self.notify(f"Play error: {e}", severity="error")

    def _refresh_queue_table(self):
        dt: DataTable = self.query_one("#queue", DataTable)
        dt.clear()
        for i, t in enumerate(self.queue.items):
            dt.add_row(str(i + 1), t.title[:40], (t.channel or "-")[:15], _fmt_duration(t.duration))
        self.query_one("#queue_label", Label).update(
            f"Queue ({len(self.queue.items)}) shuffle={'on' if self.queue.shuffle else 'off'} repeat={self.queue.repeat}"
        )

    def _poll_player(self):
        pos = self.player.get_time_pos()
        dur = self.player.get_duration()
        paused = self.player.is_paused()
        bar: ProgressBar = self.query_one("#progress", ProgressBar)
        if dur and pos is not None:
            bar.total = max(1, int(dur))
            bar.progress = int(pos)
            self._was_playing = True
            self._eof_handled = False
        # detect EOF: mpv idle after playing
        idle = self.player.is_idle()
        eof = self.player.eof_reached()
        is_eof = (eof is True) or (self._was_playing and pos is None and dur is None and idle is True and paused is not True)
        if is_eof and not self._eof_handled and self.queue.current_track() is not None:
            self._eof_handled = True
            self._was_playing = False
            self._handle_track_end()

        status = self.query_one("#status", Label)
        vol = self.player.volume
        sh = "on" if self.queue.shuffle else "off"
        ap = "on" if self.config.queue.autoplay else "off"
        status.update(f"vol {vol}% | shuffle {sh} | repeat {self.queue.repeat} | autoplay {ap} | {'⏸' if paused else '▶'}")

    def _handle_track_end(self):
        # repeat one -> replay
        if self.queue.repeat == "one":
            self._play_current()
            return
        nxt = self.queue.next_idx()
        if nxt is not None:
            self.queue.set_current(nxt)
            self._play_current()
            return
        # end of queue -> autoplay mix
        if self.config.queue.autoplay:
            cur = self.queue.current_track()
            if cur and not self._autoplay_fetching:
                self._autoplay_fetching = True

                async def _fetch_and_play():
                    try:
                        exclude = {t.id for t in self.queue.items}
                        tracks = await asyncio.to_thread(get_mix_tracks, cur, self.config.queue.mix_limit, exclude)
                        if tracks:
                            self.queue.extend(tracks)
                            self._refresh_queue_table()
                            nxt2 = self.queue.next_idx()
                            if nxt2 is not None:
                                self.queue.set_current(nxt2)
                                self._play_current()
                            else:
                                self.query_one("#now_playing", Label).update("Stopped — queue ended")
                        else:
                            self.query_one("#now_playing", Label).update("Stopped — queue ended")
                    finally:
                        self._autoplay_fetching = False

                asyncio.create_task(_fetch_and_play())
            return
        self.query_one("#now_playing", Label).update("Stopped — queue ended")

    # Actions
    def action_toggle_help(self):
        self.show_help = not self.show_help
        w = self.query_one("#help", Static)
        w.display = self.show_help

    def action_pause(self):
        self.player.pause_toggle()

    def action_next(self):
        nxt = self.queue.next_idx()
        if nxt is None:
            self.notify("End of queue")
            return
        self.queue.set_current(nxt)
        self._play_current()

    def action_prev(self):
        prv = self.queue.prev_idx()
        if prv is None:
            self.notify("Start of queue")
            return
        self.queue.set_current(prv)
        self._play_current()

    def action_vol_up(self):
        self.player.set_volume(self.player.volume + 5)

    def action_vol_down(self):
        self.player.set_volume(self.player.volume - 5)

    def action_seek_forward(self):
        self.player.seek(self.config.player.seek_secs, relative=True)

    def action_seek_back(self):
        self.player.seek(-self.config.player.seek_secs, relative=True)

    def action_add_to_queue(self):
        dt: DataTable = self.query_one("#results", DataTable)
        if dt.row_count == 0:
            return
        idx = dt.cursor_row
        if 0 <= idx < len(self.search_results):
            self.queue.add(self.search_results[idx])
            self._refresh_queue_table()
            self.notify(f"Added to queue: {self.search_results[idx].title[:30]}")

    def action_toggle_autoplay(self):
        self.config.queue.autoplay = not self.config.queue.autoplay
        self.notify(f"Autoplay {'on' if self.config.queue.autoplay else 'off'}")

    def action_play_context(self):
        self._play_context()
        self.notify("Playing context (all search results)")

    def action_toggle_shuffle(self):
        self.queue.shuffle = not self.queue.shuffle
        self._refresh_queue_table()
        self.notify(f"Shuffle {'on' if self.queue.shuffle else 'off'}")

    def action_toggle_repeat(self):
        order = ["off", "all", "one"]
        cur = order.index(self.queue.repeat) if self.queue.repeat in order else 0
        self.queue.repeat = order[(cur + 1) % len(order)]
        self._refresh_queue_table()
        self.notify(f"Repeat {self.queue.repeat}")

    def action_clear_queue(self):
        self.queue.clear()
        self._refresh_queue_table()

    def action_focus_search(self):
        self.query_one("#search_input", Input).focus()

    def on_unmount(self):
        self.player.terminate()


def run():
    cfg = AppConfig.load()
    app = MusicApp(cfg)
    app.run()
