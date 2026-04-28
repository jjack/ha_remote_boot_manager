"""DataUpdateCoordinator for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_BOOT_OPTION_NONE,
    DOMAIN,
    LOGGER,
    SAVE_DELAY,
    SIGNAL_NEW_SERVER,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant


class RemoteBootManager:
    """Class to manage remote boot options."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Central state manager for remote boot options."""
        self.hass = hass

        self._listeners: list[Callable] = []

        """
        In-memory dict to hold server information, keyed by mac to ensure uniqueness

          { "mac": {
              "hostname":        "server1",
              "broadcast_address": "192.168.1.255",
              "broadcast_port":   9,
              "bootloader":  "grub",
              "boot_options":     ["ubuntu", "windows"],
              "next_boot_option": "(none)"
          }
        """
        self.servers: dict[str, Any] = {}
        self._store = Store(hass, 1, f"{DOMAIN}.servers")

    async def async_load(self) -> None:
        """Load data from storage."""
        data = await self._store.async_load()
        if data and "servers" in data:
            self.servers = data["servers"]

    async def async_purge_data(self) -> None:
        """Purge data from storage."""
        self.servers.clear()
        await self._store.async_remove()

    @callback
    def async_remove_server(self, mac_address: str) -> None:
        """Remove a server from the manager and save state."""
        if mac_address in self.servers:
            self.servers.pop(mac_address)
            self._save()
            LOGGER.info("Removed server: %s", mac_address)

    def _save(self) -> None:
        """Save data to storage."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data for storage."""
        return {"servers": self.servers}

    @callback
    def async_add_listener(self, update_callback: Callable) -> Callable:
        """Register listeners (used by select and button entities)."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    def _notify_listeners(self) -> None:
        """Tell all registered entities to update their states."""
        for update_callback in self._listeners:
            update_callback()

    @callback
    def async_process_webhook_payload(self, mac_address: str, payload: dict) -> None:
        """Process payloads from the bare-metal GO agents."""
        hostname = payload["hostname"]
        boot_options = payload["boot_options"]
        bootloader = payload["bootloader"]
        broadcast_address = payload.get(CONF_BROADCAST_ADDRESS)
        broadcast_port = payload.get(CONF_BROADCAST_PORT)

        is_new_server = mac_address not in self.servers
        if is_new_server:
            next_boot_option = DEFAULT_BOOT_OPTION_NONE
            LOGGER.info("Discovered new server: %s (%s)", hostname, mac_address)
        else:
            next_boot_option = self.servers[mac_address].get(
                "next_boot_option", DEFAULT_BOOT_OPTION_NONE
            )
            old_hostname = self.servers[mac_address]["hostname"]

            # Update the HA device registry so the entity name updates in the UI
            if old_hostname != hostname:
                LOGGER.info(
                    "Server renamed: %s -> %s (%s)", old_hostname, hostname, mac_address
                )
                device_reg = dr.async_get(self.hass)
                device = device_reg.async_get_device(
                    identifiers={(DOMAIN, mac_address)}
                )
                if device:
                    device_reg.async_update_device(device.id, name=hostname)
            else:
                LOGGER.info(
                    "Received update for server: %s (%s) - boot options: %s",
                    hostname,
                    mac_address,
                    boot_options,
                )

        self.servers[mac_address] = {
            "hostname": hostname,
            "bootloader": bootloader,
            "boot_options": [],
            "next_boot_option": next_boot_option,
            CONF_BROADCAST_ADDRESS: broadcast_address,
            CONF_BROADCAST_PORT: broadcast_port,
        }

        # add "(none)" option to the front of the list if it's not already there
        if boot_options and boot_options[0] != DEFAULT_BOOT_OPTION_NONE:
            boot_options = [DEFAULT_BOOT_OPTION_NONE, *boot_options]

        self.servers[mac_address]["boot_options"] = boot_options

        # If the selected boot option is no longer in the list, reset it
        if (
            self.servers[mac_address]["next_boot_option"] not in boot_options
            and self.servers[mac_address]["next_boot_option"]
            != DEFAULT_BOOT_OPTION_NONE
        ):
            self.servers[mac_address]["next_boot_option"] = DEFAULT_BOOT_OPTION_NONE

        if is_new_server:
            async_dispatcher_send(self.hass, SIGNAL_NEW_SERVER, mac_address)
        else:
            self._notify_listeners()

        self._save()

    @callback
    def async_set_next_boot_option(
        self, mac_address: str, next_boot_option: str
    ) -> None:
        """Notify listeners that the selected boot option has changed."""
        if mac_address in self.servers:
            self.servers[mac_address]["next_boot_option"] = next_boot_option
            self._save()
            self._notify_listeners()
            LOGGER.debug(
                "Set selected boot option for %s to %s",
                mac_address,
                next_boot_option,
            )

    @callback
    def async_consume_next_boot_option(self, mac_address: str) -> str:
        """Retrieve the requested boot option and immediately resets the state."""
        if mac_address not in self.servers:
            LOGGER.warning(
                "GRUB requested boot option for unknown MAC address: %s", mac_address
            )
            return DEFAULT_BOOT_OPTION_NONE

        # grab the selected boot option and reset the state for next boot to
        # prevent boot loops
        next_boot_option = self.servers[mac_address]["next_boot_option"]
        self.servers[mac_address]["next_boot_option"] = DEFAULT_BOOT_OPTION_NONE
        self._save()

        # Notify UI to revert the dropdown back to "(none)"
        self._notify_listeners()

        return next_boot_option
