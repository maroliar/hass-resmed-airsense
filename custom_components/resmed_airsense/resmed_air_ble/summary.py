"""Decoder for the "Summary" logged-data spool: one protobuf record per therapy day (noon to noon).

No schema ships with the app (it uploads the blob to the cloud). Every field below was matched against the
machine's own SD-card summary (STR.edf) over 72 nights with zero mismatches; all values are the STR.edf
signal in hundredths (x 0.01). STR.edf names are given in brackets.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        s += 7
        if x < 0x80:
            return r, i


def _fields(b: bytes):
    i = 0
    while i < len(b):
        key, i = _varint(b, i)
        f, t = key >> 3, key & 7
        if t == 0:
            v, i = _varint(b, i)
        elif t == 2:
            ln, i = _varint(b, i)
            v, i = b[i : i + ln], i + ln
        elif t == 5:
            v, i = b[i : i + 4], i + 4
        elif t == 1:
            v, i = b[i : i + 8], i + 8
        else:
            raise ValueError(f"wire type {t}")
        yield f, v


def _ts(ms: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(ms / 1000, dt.UTC)


P50_95_MAX = {2: "median", 3: "p95", 4: "max"}
P50_70_95_MAX = {2: "median", 3: "p70", 4: "p95", 5: "max"}
P5_95 = {1: "p5", 3: "p95"}
P50 = {2: "median"}


def _stats(b: bytes, names: dict[int, str]) -> dict[str, float]:
    return {names[f]: round(v * 0.01, 3) for f, v in _fields(b) if isinstance(v, int) and f in names}


def _single(b: bytes) -> float | None:
    return _stats(b, P50).get("median")


@dataclass
class Session:
    start: dt.datetime
    minutes: int


@dataclass
class DailySummary:
    day_start: dt.datetime
    day_end: dt.datetime
    usage_minutes: int = 0  # [Duration]
    sessions: list[Session] = field(default_factory=list)  # [MaskOn/MaskOff]
    mask_events: int = 0  # [MaskEvents]
    ahi: float | None = None  # [AHI]
    ai: float | None = None  # [AI]
    hi: float | None = None  # [HI]
    oai: float | None = None  # [OAI] obstructive
    cai: float | None = None  # [CAI] central
    uai: float | None = None  # [UAI] unclassified
    rin: float | None = None  # [RIN] RERA index
    csr_minutes: float | None = None  # [CSR] Cheyne-Stokes respiration
    leak_lps: dict[str, float] = field(default_factory=dict)  # [Leak.50/70/95/Max] L/s
    target_pressure: dict[str, float] = field(default_factory=dict)  # [TgtIPAP.*] cmH2O
    target_epap: dict[str, float] = field(default_factory=dict)  # [TgtEPAP.*] cmH2O
    mask_pressure: dict[str, float] = field(default_factory=dict)  # [MaskPress.*] cmH2O
    tidal_volume_l: dict[str, float] = field(default_factory=dict)  # [TidVol.*] L
    minute_vent: dict[str, float] = field(default_factory=dict)  # [MinVent.*] L/min
    resp_rate: dict[str, float] = field(default_factory=dict)  # [RespRate.*] breaths/min
    blower_pressure: dict[str, float] = field(default_factory=dict)  # [BlowPress.5/95] cmH2O
    flow_lps: dict[str, float] = field(default_factory=dict)  # [Flow.5/95] L/s
    blower_flow_lps: float | None = None  # [BlowFlow.50] L/s
    ambient_humidity: float | None = None  # [AmbHumidity.50] mg/L
    humidifier_temp: float | None = None  # [HumTemp.50] C
    heated_tube_temp: float | None = None  # [HTubeTemp.50] C
    humidifier_power: float | None = None  # [HumPow.50] %
    heated_tube_power: float | None = None  # [HTubePow.50] %
    updated: dt.datetime | None = None
    raw: dict[int, Any] = field(default_factory=dict)

    @property
    def usage_hours(self) -> float:
        return round(self.usage_minutes / 60, 2)

    @property
    def mask_on_count(self) -> int:
        return self.mask_events or len(self.sessions)


def _index(v: int) -> float:
    return round(v * 0.01, 2)


def parse_record(b: bytes) -> DailySummary:
    f = {}
    sessions: list[Session] = []
    for k, v in _fields(b):
        if k == 6:
            for _, s in _fields(v):
                d = dict(_fields(s))
                sessions.append(Session(_ts(d.get(1, 0)), d.get(2, 0)))
        else:
            f[k] = v
    s = DailySummary(day_start=_ts(f.get(2, 0)), day_end=_ts(f.get(3, 0)), sessions=sessions, raw=f)
    s.usage_minutes = f.get(5, 0)
    s.mask_events = f.get(39, 0)
    if s.usage_minutes:
        s.ahi, s.ai, s.hi = _index(f.get(7, 0)), _index(f.get(8, 0)), _index(f.get(9, 0))
        s.oai, s.cai, s.uai, s.rin = (_index(f.get(k, 0)) for k in (10, 11, 12, 13))
        s.csr_minutes = f.get(16, 0) * 0.01
    for key, attr, names in (
        (14, "leak_lps", P50_70_95_MAX),
        (15, "target_pressure", P50_95_MAX),
        (20, "target_epap", P50_95_MAX),
        (21, "mask_pressure", P50_95_MAX),
        (22, "tidal_volume_l", P50_95_MAX),
        (23, "minute_vent", P50_95_MAX),
        (25, "resp_rate", P50_95_MAX),
        (36, "blower_pressure", P5_95),
        (37, "flow_lps", P5_95),
    ):
        if isinstance(f.get(key), bytes):
            setattr(s, attr, _stats(f[key], names))
    for key, attr in (
        (38, "blower_flow_lps"),
        (29, "ambient_humidity"),
        (30, "humidifier_temp"),
        (31, "heated_tube_temp"),
        (32, "humidifier_power"),
        (33, "heated_tube_power"),
    ):
        if isinstance(f.get(key), bytes):
            setattr(s, attr, _single(f[key]))
    if 40 in f:
        s.updated = _ts(f[40])
    return s


def parse_summary_spool(data: bytes) -> list[DailySummary]:
    """All day records in the spool, oldest first."""
    return [parse_record(v) for k, v in _fields(data) if k == 2 and isinstance(v, bytes)]


def last_night(days: list[DailySummary]) -> DailySummary | None:
    """Most recent day with therapy use."""
    used = [d for d in days if d.usage_minutes > 0]
    return used[-1] if used else None
