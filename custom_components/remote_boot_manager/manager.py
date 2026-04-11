"""DataUpdateCoordinator for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

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
