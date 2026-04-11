"""DataUpdateCoordinator for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DEFAULT_OS_NONE, DOMAIN, LOGGER

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
        In-memory dict to hold server information, keyed by mac because hostnames
        can change and may not be unique.

          { "mac_address1": {
              "hostname": "server1",
              "bootloader": "grub",
              "os_list": ["ubuntu", "windows"],
              "selected_os": "(none)"
          }
        """
        self.servers: dict[str, Any] = {}

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
        hostname = payload.get("hostname", "unknown_host")
        os_list = payload.get("os_list", [])
        bootloader = payload.get("bootloader", "grub")

        is_new_server = mac_address not in self.servers

        if is_new_server:
            LOGGER.info("Discovered new server: %s (%s)", hostname, mac_address)
            self.servers[mac_address] = {
                "hostname": hostname,
                "bootloader": bootloader,
                "os_list": [],
                "selected_os": DEFAULT_OS_NONE,
            }
        else:
            self.servers[mac_address]["bootloader"] = bootloader

        self.servers[mac_address]["os_list"] = os_list

        # If the selected OS is no longer in the list, reset it
        if (
            self.servers[mac_address]["selected_os"] not in os_list
            and self.servers[mac_address]["selected_os"] != DEFAULT_OS_NONE
        ):
            self.servers[mac_address]["selected_os"] = DEFAULT_OS_NONE

        if is_new_server:
            async_dispatcher_send(self.hass, f"{DOMAIN}_new_server", mac_address)
        else:
            self._notify_listeners()
