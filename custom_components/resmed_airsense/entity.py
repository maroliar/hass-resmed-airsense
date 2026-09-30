"""Base entity for the AirSense."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import CONF_SERIAL, DOMAIN
from .coordinator import AirSenseCoordinator


class AirSenseEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: AirSenseCoordinator, description: EntityDescription) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        serial = coordinator.entry.data.get(CONF_SERIAL)
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            manufacturer="ResMed",
            name=coordinator.entry.title,
            serial_number=serial,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
