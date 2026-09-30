"""Diagnostics download: everything the coordinator knows, with keys and identifiers redacted."""
from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import AirSenseConfigEntry
from .const import CONF_CLIENT_ID, CONF_MASTER_PAIR_KEY, CONF_SERIAL

TO_REDACT = {
    CONF_MASTER_PAIR_KEY,
    CONF_CLIENT_ID,
    CONF_SERIAL,
    "SerialNumber",
    "UniversalIdentifier",
    "HardwareIdentifier",
    "IMEI",
    "ServiceHost",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: AirSenseConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    d = c.data
    night = dataclasses.asdict(d.last_night) if d.last_night else None
    if night:
        night.pop("raw", None)
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "connected": c.connected,
        "events": d.events,
        "live": d.live,
        "settings": d.settings,
        "metrics": d.metrics,
        "identity": async_redact_data(d.identity, TO_REDACT),
        "version": async_redact_data(d.version, TO_REDACT),
        "cellular": async_redact_data(d.cellular, TO_REDACT),
        "last_night": night,
        # raw field numbers of every stored day, to help decode the fields that are still unknown
        "days_raw": [{str(k): v for k, v in day.raw.items() if isinstance(v, int)} for day in d.days],
    }
