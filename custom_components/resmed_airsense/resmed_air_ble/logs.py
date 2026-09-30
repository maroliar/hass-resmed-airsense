"""Decoders for the small device logs (spools): cloud upload activity and SoundCheck runs.

CellularActivityEvents: one record per modem event {1: code, 2: time ms, 3: time ms, 6: HTTP status, 16: item}.
Observed upload session after each therapy night (codes inferred from their order and HTTP statuses):
  23 start, 6 modem on, 10 registered, 13 HTTP response (6 = status), 16 authorised,
  24 item sent (16 = item id), 11 session end.
SoundcheckVector: one record per SoundCheck run {1: time ms, 2: sample rate?, 3: [...], 4: [...]}.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .summary import _fields, _ts

EV_HTTP, EV_ITEM_SENT, EV_END = 13, 24, 11


@dataclass
class CloudUpload:
    start: dt.datetime
    end: dt.datetime | None = None
    http_statuses: list[int] = field(default_factory=list)
    items_sent: int = 0

    @property
    def ok(self) -> bool:
        return bool(self.http_statuses) and all(200 <= s < 300 for s in self.http_statuses) and self.end is not None


def parse_cloud_uploads(data: bytes) -> list[CloudUpload]:
    """Upload sessions, oldest first."""
    events: list[dict[int, int]] = []
    for _, rec in _fields(data):
        if isinstance(rec, bytes):
            events += [dict(_fields(ev)) for f, ev in _fields(rec) if f == 1 and isinstance(ev, bytes)]
    sessions: list[CloudUpload] = []
    for ev in sorted(events, key=lambda e: e.get(2, 0)):
        code, when = ev.get(1), _ts(ev.get(2, 0))
        # 23 also precedes every item inside a session; a new session starts only after the previous one ended
        if not sessions or sessions[-1].end is not None:
            sessions.append(CloudUpload(start=when))
        cur = sessions[-1]
        if code == EV_HTTP and 6 in ev:
            cur.http_statuses.append(ev[6])
        elif code == EV_ITEM_SENT:
            cur.items_sent += 1
        elif code == EV_END:
            cur.end = when
    return sessions


def parse_soundchecks(data: bytes) -> list[dt.datetime]:
    """Start times of SoundCheck runs, oldest first (each run logs a few vectors seconds apart)."""
    times = sorted(
        _ts(d[1])
        for f, rec in _fields(data)
        if f == 15 and isinstance(rec, bytes) and 1 in (d := {k: v for k, v in _fields(rec) if k == 1})
    )
    runs: list[dt.datetime] = []
    for t in times:
        if not runs or t - runs[-1] > dt.timedelta(minutes=10):
            runs.append(t)
    return runs
