"""Select platform for Remote Boot Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DEFAULT_BOOT_OPTION_NONE, DOMAIN, LOGGER, SIGNAL_NEW_SERVER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .manager import RemoteBootManager

ENTITY_DESCRIPTIONS = (
    SelectEntityDescription(
        key="remote_boot_manager_select",
        name="Remote Boot Manager Select",
        icon="mdi:harddisk",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    manager = entry.runtime_data

    @callback
    def async_add_server_select(mac_address: str) -> None:
        """Add a select entity for a newly discovered server."""
        LOGGER.debug("Adding select entity for %s", mac_address)
        async_add_entities([RemoteBootManagerSelect(manager, mac_address)])

    # Add entities for servers that already exist in the manager
    for mac in manager.servers:
        async_add_server_select(mac)

    # Listen for the signal to add new servers discovered via webhook
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_SERVER, async_add_server_select)
    )


class RemoteBootManagerSelect(SelectEntity):
    """remote_boot_manager select class."""

    def __init__(self, manager: RemoteBootManager, mac_address: str) -> None:
        """Initialize the select entity."""
        self.manager = manager
        self.mac_address = mac_address

        # This ties the entity to a specific hardware device in HA
        self._attr_unique_id = f"{mac_address}_boot_option_select"
        self._attr_name = "Next Boot Option"
        self._attr_has_entity_name = True

        server_data = self.manager.servers[mac_address]

        broadcast_info = []
        if broadcast_address := server_data.broadcast_address:
            broadcast_info.append(f"Broadcast: {broadcast_address}")
        if broadcast_port := server_data.broadcast_port:
            broadcast_info.append(f"Port: {broadcast_port}")

        model_name = (
            f"Wake-on-LAN ({', '.join(broadcast_info)})"
            if broadcast_info
            else "Wake-on-LAN"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=server_data.name,
            manufacturer="Remote Boot Manager",
            model=model_name,
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available boot options."""
        server_data = self.manager.servers.get(self.mac_address)
        opts = (
            server_data.boot_options if server_data and server_data.boot_options else []
        )

        # Ensure the default "(none)" is always a valid option
        if DEFAULT_BOOT_OPTION_NONE not in opts:
            opts = [DEFAULT_BOOT_OPTION_NONE, *opts]

        return opts

    @property
    def current_option(self) -> str | None:
        """Return the currently pending boot option."""
        server_data = self.manager.servers.get(self.mac_address)
        return (
            server_data.next_boot_option
            if server_data and server_data.next_boot_option
            else DEFAULT_BOOT_OPTION_NONE
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.manager.async_set_next_boot_option(self.mac_address, option)

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # Subscribe to manager updates so the UI redraws when webhooks arrive
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_update_{self.mac_address}",
                self.async_write_ha_state,
            )
        )
