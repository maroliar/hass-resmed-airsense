"""Dev CLI.

  python -m resmed_air_ble pair    <MAC> <creds.json>      # machine in pairing mode; asks the screen code
                                                           # (no tty: waits for it in /tmp/as11_passkey)
  python -m resmed_air_ble monitor <MAC> <creds.json> [s]  # reconnect and print FGState live
"""
from __future__ import annotations

import asyncio
import datetime
import json
import pathlib
import sys

from bleak import BleakClient, BleakScanner

from . import AirSenseClient, Credentials, FG_THERAPY_STATES


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


async def _connect(mac: str) -> BleakClient:
    print(f"[{_ts()}] scanning {mac}...")
    dev = await BleakScanner.find_device_by_address(mac, timeout=25)
    if not dev:
        raise SystemExit("device not advertising (wake it / enter pairing mode)")
    ble = BleakClient(dev)
    await ble.connect()
    print(f"[{_ts()}] connected")
    return ble


async def _read_code() -> str:
    if sys.stdin.isatty():
        return (await asyncio.to_thread(input, "code shown on the device screen: ")).strip()
    f = pathlib.Path("/tmp/as11_passkey")
    f.unlink(missing_ok=True)
    print(f"[{_ts()}] waiting for the screen code in {f}...", flush=True)
    for _ in range(1800):
        if f.exists() and f.read_text().strip():
            return f.read_text().strip()
        await asyncio.sleep(0.5)
    raise SystemExit("no code received")


async def pair(mac: str, path: pathlib.Path) -> None:
    ble = await _connect(mac)
    try:
        c = AirSenseClient(ble)
        await c.start()
        code = await _read_code()
        creds = await c.pair(code)
        path.write_text(json.dumps(creds.as_dict(), indent=2))
        print(f"[{_ts()}] paired, clientId={creds.client_id}; saved to {path}")
        print(await c.get("SerialNumber", "FGState"))
        await c.stop()
    finally:
        await ble.disconnect()


async def monitor(mac: str, path: pathlib.Path, secs: int) -> None:
    creds = Credentials.from_dict(json.loads(path.read_text()))
    last: dict[str, str] = {}

    def on_event(data_id, value, _ev):
        print(f"[{_ts()}] {data_id} = {value}")
        if data_id == "FGState":
            if last.get(data_id) in FG_THERAPY_STATES and value not in FG_THERAPY_STATES:
                print(f"[{_ts()}] ALARM: therapy stopped ({last[data_id]} -> {value})")
            last[data_id] = value

    ble = await _connect(mac)
    try:
        c = AirSenseClient(ble, on_event)
        await c.start()
        await c.open_session(creds)
        print(f"[{_ts()}] session open")
        print(await c.subscribe())
        await asyncio.sleep(secs)
        await c.stop()
    finally:
        await ble.disconnect()


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[1] not in ("pair", "monitor"):
        raise SystemExit(__doc__)
    mac, path = sys.argv[2], pathlib.Path(sys.argv[3])
    if sys.argv[1] == "pair":
        asyncio.run(pair(mac, path))
    else:
        asyncio.run(monitor(mac, path, int(sys.argv[4]) if len(sys.argv) > 4 else 300))


if __name__ == "__main__":
    main()
