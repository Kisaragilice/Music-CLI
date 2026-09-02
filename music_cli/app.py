from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, Label, ProgressBar, Static

from .config import AppConfig
from .player import MpvPlayer
from .queue import Queue
from .search import Track, _fmt_duration, search_ytdlp


HELP_TEXT = """\
[q] quit  [?] help  [enter] play  [space] pause  [n] next  [p] prev
[+/-] vol  [</>] seek 5s  [z] queue  [s] shuffle  [r] repeat  [c] clear queue
[/] focus search  [j/k] nav  [G/gg] top/bottom
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
    ]

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self.config = config or AppConfig.load()
        self.player = MpvPlayer(ytdl_format=self.config.player.ytdl_format, volume=self.config.player.volume)
        self.queue = Queue()
        self.search_results: list[Track] = []
        self.show_help = False

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
            tracks = await asyncio.to_thread(search_ytdlp, query, self.config.ui.page_size)
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
        # add all results to queue if queue empty, or just play selected
        if not self.queue.items:
            for t in self.search_results:
                self.queue.add(t)
            self.queue.set_current(idx)
        else:
            # play immediately, insert after current
            self.queue.add_next(track)
            self.queue.set_current(self.queue.current + 1 if self.queue.current >= 0 else len(self.queue.items) - 1)
        self._refresh_queue_table()
        self._play_current()

    def _play_current(self):
        track = self.queue.current_track()
        if not track:
            return
        self.query_one("#now_playing", Label).update(f"▶ {track.title} — {track.channel or ''}")
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
        # update progress and auto-next on EOF
        pos = self.player.get_time_pos()
        dur = self.player.get_duration()
        paused = self.player.is_paused()
        bar: ProgressBar = self.query_one("#progress", ProgressBar)
        if dur and pos is not None:
            bar.total = max(1, int(dur))
            bar.progress = int(pos)
            # auto-next when near end (mpv will idle, we detect eof via idle)
            if dur - pos < 0.8:
                # will be handled by next poll if stopped
                pass
        # detect stopped (no time-pos but queue has next)
        if pos is None and dur is None and self.queue.current_track() is not None:
            # check if mpv is idle (paused None?) — simple: if not paused and pos None -> track ended
            # try to auto next after 1s delay — we do it via checking that time-pos is None and not paused
            # To avoid immediate loop, check if player is not paused and we have next
            # For MVP, just don't auto-advance automatically; user presses n
            pass
        status = self.query_one("#status", Label)
        vol = self.player.volume
        sh = "on" if self.queue.shuffle else "off"
        status.update(f"vol {vol}% | shuffle {sh} | repeat {self.queue.repeat} | {'⏸' if paused else '▶'}")

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
