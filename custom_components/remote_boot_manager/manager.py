"""DataUpdateCoordinator for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
