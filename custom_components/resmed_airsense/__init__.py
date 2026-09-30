"""ResMed AirSense (local Bluetooth) — live therapy state from the CPAP, no cloud."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AirSenseCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type AirSenseConfigEntry = ConfigEntry[AirSenseCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirSenseConfigEntry) -> bool:
    coordinator = AirSenseCoordinator(hass, entry)
    entry.runtime_data = coordinator
    await coordinator.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirSenseConfigEntry) -> bool:
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
