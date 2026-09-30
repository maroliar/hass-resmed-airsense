"""Config flow: discover the machine, connect, type the code shown on its screen (SRP pairing)."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

import voluptuous as vol
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_CLIENT_ID, CONF_MASTER_PAIR_KEY, CONF_PASSKEY, CONF_SERIAL, DOMAIN
from .resmed_air_ble import NAME_PREFIX, SERVICE_UUID, AirSenseClient, AirSenseError, AuthError

_LOGGER = logging.getLogger(__name__)


def _is_airsense(info: bluetooth.BluetoothServiceInfoBleak) -> bool:
    return SERVICE_UUID in info.service_uuids or (info.name or "").startswith(NAME_PREFIX)


class AirSenseConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name: str | None = None
        self._discovered: dict[str, str] = {}
        self._ble: Any = None
        self._client: AirSenseClient | None = None

    # ---- entry points -----------------------------------------------------------------

    async def async_step_bluetooth(self, discovery_info: bluetooth.BluetoothServiceInfoBleak) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._address, self._name = discovery_info.address, discovery_info.name
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_connect()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._address = user_input[CONF_ADDRESS]
            self._name = self._discovered[self._address]
            await self.async_set_unique_id(self._address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_connect()
        configured = self._async_current_ids(include_ignore=False)
        for info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if _is_airsense(info) and info.address not in configured:
                self._discovered[info.address] = info.name or info.address
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._discovered)}),
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._address = entry_data[CONF_ADDRESS]
        self._name = self._get_reauth_entry().title
        return await self.async_step_connect()

    # ---- pairing ------------------------------------------------------------------------

    async def async_step_connect(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Instructions; on submit, open the BLE link and keep it for the code step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._async_connect()
            except (AirSenseError, BleakError, TimeoutError) as err:
                _LOGGER.debug("connect failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_code()
        return self.async_show_form(
            step_id="connect", errors=errors, description_placeholders={"name": self._name or ""}
        )

    async def async_step_code(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                creds = await self._client.pair(user_input[CONF_PASSKEY].strip())
                serial = (await self._client.get("SerialNumber")).get("SerialNumber")
            except AuthError:
                errors["base"] = "invalid_code"
            except (AirSenseError, BleakError, TimeoutError, ValueError) as err:
                _LOGGER.debug("pairing failed: %s", err)
                await self._async_disconnect()
                errors["base"] = "cannot_connect"
                return self.async_show_form(step_id="connect", errors=errors,
                                            description_placeholders={"name": self._name or ""})
            else:
                await self._async_disconnect()
                data = {
                    CONF_ADDRESS: self._address,
                    CONF_CLIENT_ID: creds.client_id,
                    CONF_MASTER_PAIR_KEY: creds.master_pair_key.hex().upper(),
                    CONF_SERIAL: serial,
                }
                if self.source == "reauth":
                    return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
                return self.async_create_entry(title=f"AirSense {serial or self._name}", data=data)
        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema({vol.Required(CONF_PASSKEY): str}),
            errors=errors,
        )

    async def _async_connect(self) -> None:
        await self._async_disconnect()
        device = bluetooth.async_ble_device_from_address(self.hass, self._address, connectable=True)
        if device is None:
            raise AirSenseError("device not in range of a connectable adapter/proxy")
        self._ble = await establish_connection(BleakClientWithServiceCache, device, self._name or self._address)
        self._client = AirSenseClient(self._ble)
        await self._client.start()

    async def _async_disconnect(self) -> None:
        if self._client:
            await self._client.stop()
            self._client = None
        if self._ble:
            with contextlib.suppress(Exception):
                await self._ble.disconnect()
            self._ble = None

    def async_remove(self) -> None:
        """Flow aborted/closed: drop the BLE link."""
        if self._ble:
            self.hass.async_create_task(self._async_disconnect())
