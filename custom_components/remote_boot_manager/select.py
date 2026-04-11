"""Select platform for Remote Boot Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    CONNECTION_NETWORK_MAC,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_OS_NONE, DOMAIN, LOGGER

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
        async_dispatcher_connect(hass, f"{DOMAIN}_new_server", async_add_server_select)
    )


class RemoteBootManagerSelect(SelectEntity, RestoreEntity):
    """remote_boot_manager select class."""

    def __init__(self, manager: RemoteBootManager, mac_address: str) -> None:
        """Initialize the select entity."""
        self.manager = manager
        self.mac_address = mac_address

        # This ties the entity to a specific hardware device in HA
        self._attr_unique_id = f"{mac_address}_os_select"
        self._attr_name = "Next Boot OS"
        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=self.manager.servers.get(mac_address, {}).get(
                "name", "Unknown Server"
            ),
            manufacturer="Remote Boot Manager",
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )

    @property
    def options(self) -> list[str]:
        """Return the list of available OS options."""
        server_data = self.manager.servers.get(self.mac_address, {})
        opts = server_data.get("os_list", [])

        # Ensure the default reset state is always a valid option
        if DEFAULT_OS_NONE not in opts:
            opts = [DEFAULT_OS_NONE, *opts]

        return opts

    @property
    def current_option(self) -> str | None:
        """Return the currently pending OS."""
        server_data = self.manager.servers.get(self.mac_address, {})
        return server_data.get("selected_os", DEFAULT_OS_NONE)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.manager.async_set_selected_os(self.mac_address, option)

    async def async_added_to_hass(self) -> None:
        """Run when the entity is added to Home Assistant."""
        await super().async_added_to_hass()

        # restore the previous state if HASS restarted
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in self.options:
            LOGGER.debug(
                "Restoring previous OS state for %s: %s",
                self.mac_address,
                last_state.state,
            )
            self.manager.async_set_selected_os(self.mac_address, last_state.state)

        # Subscribe to manager updates so the UI redraws when webhooks arrive
        self.async_on_remove(self.manager.async_add_listener(self.async_write_ha_state))
