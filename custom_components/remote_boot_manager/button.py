"""Button platform for Remote Boot Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wakeonlan
from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import RemoteBootManagerConfigEntry
    from .manager import RemoteBootManager


ENTITY_DESCRIPTIONS = (
    ButtonEntityDescription(
        key="remote_boot_manager_button",
        name="Integration Button",
        icon="mdi:gesture-tap-button",
        device_class=ButtonDeviceClass.RESTART,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    manager = entry.runtime_data

    @callback
    def async_add_server_select(mac_address: str) -> None:
        """Add a select entity for a newly discovered server."""
        async_add_entities([RemoteBootManagerButton(manager, mac_address)])

    # Add entities for servers that already exist in the manager
    for mac in manager.servers:
        async_add_server_select(mac)

    # Listen for the signal to add new servers discovered via webhook
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_server", async_add_server_select)
    )


class RemoteBootManagerButton(ButtonEntity):
    """Remote Boot Manager button class."""

    def __init__(
        self,
        manager: RemoteBootManager,
        mac_address: str,
    ) -> None:
        """Initialize the button class."""
        self.manager = manager
        self.mac_address = mac_address

        self._attr_unique_id = f"{mac_address}_wake_button"
        self._attr_name = "Wake Server"
        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=self.manager.servers.get(mac_address, {}).get(
                "hostname", "Unknown Server"
            ),
            manufacturer="Remote Boot Manager",
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        # wakeonlan is blocking, so it needs run in the executor queue
        await self.hass.async_add_executor_job(
            wakeonlan.send_magic_packet, self.mac_address
        )
