"""Therapy running (the alarm trigger) and link status."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirSenseConfigEntry
from .entity import AirSenseEntity

THERAPY = BinarySensorEntityDescription(
    key="therapy", translation_key="therapy", device_class=BinarySensorDeviceClass.RUNNING
)
CONNECTED = BinarySensorEntityDescription(
    key="connected", translation_key="connected",
    device_class=BinarySensorDeviceClass.CONNECTIVITY, entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AirSenseConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities([TherapySensor(c, THERAPY), ConnectedSensor(c, CONNECTED)])


class TherapySensor(AirSenseEntity, BinarySensorEntity):
    """On while the blower runs (Therapy/MaskFit/...). on->off = mask removed (AutoStop) or end of night."""

    @property
    def available(self) -> bool:
        return self.coordinator.connected and "FGState" in self.coordinator.data.events

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.therapy_running


class ConnectedSensor(AirSenseEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        return self.coordinator.connected
