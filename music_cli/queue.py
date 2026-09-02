from __future__ import annotations

import random
from dataclasses import dataclass, field

from .search import Track


@dataclass
class Queue:
    items: list[Track] = field(default_factory=list)
    current: int = -1  # index of now playing
    shuffle: bool = False
    repeat: str = "off"  # off|all|one

    def add(self, track: Track):
        # dedup by id
        if any(t.id == track.id for t in self.items):
            return
        self.items.append(track)

    def extend(self, tracks: list[Track]):
        for t in tracks:
            self.add(t)

    def add_next(self, track: Track):
        if self.current < 0:
            self.items.append(track)
        else:
            self.items.insert(self.current + 1, track)

    def current_track(self) -> Track | None:
        if 0 <= self.current < len(self.items):
            return self.items[self.current]
        return None

    def set_current(self, idx: int):
        if 0 <= idx < len(self.items):
            self.current = idx

    def next_idx(self) -> int | None:
        if not self.items:
            return None
        if self.repeat == "one":
            return self.current
        if self.shuffle:
            if len(self.items) == 1:
                return 0
            # pick random != current
            choices = [i for i in range(len(self.items)) if i != self.current]
            return random.choice(choices)
        nxt = self.current + 1
        if nxt < len(self.items):
            return nxt
        if self.repeat == "all":
            return 0
        return None

    def prev_idx(self) -> int | None:
        if not self.items:
            return None
        if self.shuffle:
            # just go linear back for simplicity
            pass
        prv = self.current - 1
        if prv >= 0:
            return prv
        if self.repeat == "all":
            return len(self.items) - 1
        return None

    def clear(self):
        self.items.clear()
        self.current = -1
