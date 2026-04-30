"""DataUpdateCoordinator for remote_boot_manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
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
    from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class RemoteServer:
    """Represents the state of a remote bare-metal server."""

    mac: str
    name: str
    host: str | None = None
    bootloader: str | None = None
    boot_options: list[str] = field(default_factory=list)
    broadcast_address: str | None = None
    broadcast_port: int | None = None
    entity_type: str = "button"

    # this comes from the UI, not the webhook
    next_boot_option: str = DEFAULT_BOOT_OPTION_NONE

    # this comes from the YAML config for wake_on_lan backwards compatibility
    off_action: list[Any] | None = None

    def update_from_payload(self, payload: dict[str, Any]) -> None:
        """Safely update the server state from incoming webhook data."""
        self.name = payload.get("name", self.name)
        self.bootloader = payload.get("bootloader", self.bootloader)
        self.boot_options = payload.get("boot_options", self.boot_options) or []
        self.host = payload.get("host", self.host)
        self.broadcast_address = payload.get(
            CONF_BROADCAST_ADDRESS, self.broadcast_address
        )
        self.broadcast_port = payload.get(CONF_BROADCAST_PORT, self.broadcast_port)
        self.entity_type = payload.get("entity_type", self.entity_type)


class RemoteBootManager:
    """Class to manage remote boot options."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Central state manager for remote boot options."""
        self.hass = hass

        self.servers: dict[str, RemoteServer] = {}
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
        mac_address = format_mac(mac_address)
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
    def async_process_webhook_payload(
        self, mac_address: str, payload: dict[str, Any]
    ) -> None:
        """Process payloads from the bare-metal GO agents."""
        mac_address = format_mac(mac_address)

        is_new_server = mac_address not in self.servers
        if is_new_server:
            self.servers[mac_address] = RemoteServer(
                mac=mac_address,
                name=payload["name"],
                bootloader=payload.get("bootloader"),
                boot_options=payload.get("boot_options") or [],
                host=payload.get("host"),
                broadcast_address=payload.get(CONF_BROADCAST_ADDRESS),
                broadcast_port=payload.get(CONF_BROADCAST_PORT),
                entity_type=payload.get("entity_type", "button"),
            )

            LOGGER.info(
                "Discovered new server: %s (%s)",
                self.servers[mac_address].name,
                mac_address,
            )
        else:
            old_name = self.servers[mac_address].name

            self.servers[mac_address].update_from_payload(payload)

            # Update the HA device registry so the entity name updates in the UI
            if old_name != self.servers[mac_address].name:
                LOGGER.info(
                    "Server renamed: %s -> %s (%s)",
                    old_name,
                    self.servers[mac_address].name,
                    mac_address,
                )
                device_reg = dr.async_get(self.hass)
                device = device_reg.async_get_device(
                    identifiers={(DOMAIN, mac_address)}
                )
                if device:
                    device_reg.async_update_device(
                        device.id, name=self.servers[mac_address].name
                    )
            else:
                LOGGER.info(
                    "Received update for server: %s (%s) - boot options: %s",
                    self.servers[mac_address].name,
                    mac_address,
                    self.servers[mac_address].boot_options,
                )

        # add "(none)" option to the front of the list if it's not already there
        current_options = self.servers[mac_address].boot_options
        if not current_options:
            boot_options = [DEFAULT_BOOT_OPTION_NONE]
        elif current_options[0] != DEFAULT_BOOT_OPTION_NONE:
            boot_options = [DEFAULT_BOOT_OPTION_NONE, *current_options]
        else:
            # It's already in the correct format
            boot_options = current_options

        self.servers[mac_address].boot_options = boot_options

        # If the selected boot option is no longer in the list, reset it
        if (
            self.servers[mac_address].next_boot_option not in boot_options
            and self.servers[mac_address].next_boot_option != DEFAULT_BOOT_OPTION_NONE
        ):
            self.servers[mac_address].next_boot_option = DEFAULT_BOOT_OPTION_NONE

        if is_new_server:
            async_dispatcher_send(self.hass, SIGNAL_NEW_SERVER, mac_address)
        else:
            async_dispatcher_send(self.hass, f"{DOMAIN}_update_{mac_address}")

        self._save()

    @callback
    def async_set_next_boot_option(
        self, mac_address: str, next_boot_option: str
    ) -> None:
        """Notify listeners that the selected boot option has changed."""
        mac_address = format_mac(mac_address)
        if mac_address in self.servers:
            self.servers[mac_address].next_boot_option = next_boot_option
            self._save()
            async_dispatcher_send(self.hass, f"{DOMAIN}_update_{mac_address}")
            LOGGER.debug(
                "Set selected boot option for %s to %s",
                mac_address,
                next_boot_option,
            )

    @callback
    def async_consume_next_boot_option(self, mac_address: str) -> str:
        """Retrieve the requested boot option and immediately resets the state."""
        mac_address = format_mac(mac_address)
        if mac_address not in self.servers:
            LOGGER.warning(
                "GRUB requested boot option for unknown MAC address: %s", mac_address
            )
            return DEFAULT_BOOT_OPTION_NONE

        # grab the selected boot option and reset the state for next boot to
        # prevent boot loops
        next_boot_option = self.servers[mac_address].next_boot_option
        self.servers[mac_address].next_boot_option = DEFAULT_BOOT_OPTION_NONE
        self._save()

        # Notify UI to revert the dropdown back to "(none)"
        async_dispatcher_send(self.hass, f"{DOMAIN}_update_{mac_address}")

        return next_boot_option
