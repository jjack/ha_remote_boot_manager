"""Button platform for Remote Boot Manager."""

from __future__ import annotations

from functools import partial
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

from .const import DOMAIN, SIGNAL_NEW_SERVER

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
        async_dispatcher_connect(hass, SIGNAL_NEW_SERVER, async_add_server_select)
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

        server_data = self.manager.servers[mac_address]

        broadcast_info = []
        if b_addr := server_data.broadcast_address:
            broadcast_info.append(f"IP: {b_addr}")
        if b_port := server_data.broadcast_port:
            broadcast_info.append(f"Port: {b_port}")

        model_name = (
            f"Wake-on-LAN ({', '.join(broadcast_info)})"
            if broadcast_info
            else "Wake-on-LAN"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=server_data.hostname,
            manufacturer="Remote Boot Manager",
            model=model_name,
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        kwargs = {}
        server = self.manager.servers.get(self.mac_address)
        if not server:
            return

        if broadcast_address := server.broadcast_address:
            kwargs["ip_address"] = broadcast_address
        if broadcast_port := server.broadcast_port:
            kwargs["port"] = broadcast_port

        # wakeonlan is blocking, so it needs run in the executor queue
        await self.hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, self.mac_address, **kwargs)
        )
