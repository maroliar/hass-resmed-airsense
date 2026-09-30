"""Tiny protobuf writer to build synthetic Summary records for tests."""


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def field(num: int, value) -> bytes:
    if isinstance(value, int):
        return varint(num << 3) + varint(value)
    if isinstance(value, dict):
        value = b"".join(field(k, v) for k, v in value.items())
    if isinstance(value, list):
        return b"".join(field(num, v) for v in value)
    return varint(num << 3 | 2) + varint(len(value)) + value


def summary_day(start_ms: int, usage: int, sessions: list[tuple[int, int]]) -> bytes:
    rec = b"".join([
        field(1, 1), field(2, start_ms), field(3, start_ms + 86_400_000), field(4, 120), field(5, usage),
        field(6, b"".join(field(1, {1: s, 2: m}) for s, m in sessions)),
        field(7, 90), field(8, 70), field(9, 10), field(10, 30), field(11, 30), field(12, 0), field(13, 0),
        field(14, {2: 20, 3: 24, 4: 44, 5: 68}), field(15, {2: 1020, 3: 1140, 4: 1260}),
        field(20, {2: 720, 3: 852, 4: 960}), field(21, {2: 800, 3: 912, 4: 1008}),
        field(22, {2: 48, 3: 80, 4: 112}), field(23, {2: 725, 3: 1113, 4: 1450}), field(25, {2: 1440, 3: 1920, 4: 2960}),
        field(29, {2: 1560}), field(30, {2: 2320}), field(32, {2: 760}),
        field(36, {1: 474, 3: 1090}), field(37, {1: 16, 3: 50}), field(38, {2: 64}), field(39, len(sessions)),
        field(40, start_ms + 50_000_000),
    ])
    return field(2, rec)


def cloud_session(t0_ms: int, statuses=(200, 202, 202, 202), end=True) -> bytes:
    """CellularActivityEvents record: one upload session."""
    evs = [(23, 0, {}), (6, 1, {}), (10, 10, {})]
    t = 12
    for i, st in enumerate(statuses):
        evs.append((13, t, {6: st}))
        if i:
            evs.append((24, t + 1, {16: i}))
        t += 2
    if end:
        evs.append((11, t + 5, {}))
    body = b"".join(field(1, {1: code, 2: t0_ms + dt * 1000, 3: t0_ms + dt * 1000, **extra}) for code, dt, extra in evs)
    return field(12, body)


def soundcheck_run(t0_ms: int) -> bytes:
    return b"".join(field(15, {1: t0_ms + i * 3000, 2: 18750}) for i in range(3))
