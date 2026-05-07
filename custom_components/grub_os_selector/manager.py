"""DataUpdateCoordinator for grub_os_selector."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
)
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
    SIGNAL_NEW_HOST,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass(slots=True)
class RemoteHost:
    """Represents the state of a remote bare-metal host."""

    mac: str
    name: str
    address: str | None = None
    boot_options: list[str] = field(default_factory=list)
    broadcast_address: str | None = None
    broadcast_port: int | None = None

    # this comes from the UI, not the webhook
    next_boot_option: str = DEFAULT_BOOT_OPTION_NONE

    # this also comes from the UI
    off_action: list[dict[str, Any]] | None = None

    def update_from_payload(self, payload: dict[str, Any]) -> None:
        """Safely update the host state from incoming webhook data."""
        self.name = payload.get("name", self.name)
        self.address = payload.get(CONF_ADDRESS, self.address)
        self.boot_options = payload.get("boot_options", self.boot_options) or []
        self.broadcast_address = payload.get(
            CONF_BROADCAST_ADDRESS, self.broadcast_address
        )
        self.broadcast_port = payload.get(CONF_BROADCAST_PORT, self.broadcast_port)


class GrubOSSelectManager:
    """Class to manage remote boot options."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Central state manager for remote boot options."""
        self.hass = hass

        self.hosts: dict[str, RemoteHost] = {}
        self._store = Store(hass, 1, f"{DOMAIN}.hosts")

    async def async_load(self) -> None:
        """Load data from storage."""
        data = await self._store.async_load()
        if data and "hosts" in data:
            self.hosts = {}
            for mac, host_data in data["hosts"].items():
                if isinstance(host_data, dict):
                    # Strip unrecognized keys from legacy storage data to prevent
                    # dataclass instantiation errors if the underlying data model has
                    # changed since the data was saved.
                    valid_keys = {f.name for f in dataclasses.fields(RemoteHost)}
                    filtered_data = {
                        k: v for k, v in host_data.items() if k in valid_keys
                    }
                    self.hosts[mac] = RemoteHost(**filtered_data)
                else:
                    LOGGER.warning(
                        "Discarding invalid host data for %s: %s", mac, host_data
                    )

    async def async_purge_data(self) -> None:
        """Purge data from storage."""
        self.hosts.clear()
        await self._store.async_remove()

    @callback
    def async_remove_host(self, mac_address: str) -> None:
        """Remove a host from the manager and save state."""
        mac_address = format_mac(mac_address)
        if mac_address in self.hosts:
            self.hosts.pop(mac_address)
            self.save()
            LOGGER.info("Removed host: %s", mac_address)

    def save(self) -> None:
        """Save data to storage."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data for storage."""
        return {
            "hosts": {mac: dataclasses.asdict(host) for mac, host in self.hosts.items()}
        }

    @callback
    def async_process_webhook_payload(
        self, mac_address: str, payload: dict[str, Any]
    ) -> None:
        """Process payloads from the bare-metal GO grub os reporters."""
        mac_address = format_mac(mac_address)

        is_new_host = mac_address not in self.hosts
        if is_new_host:
            self.hosts[mac_address] = RemoteHost(
                mac=mac_address,
                name=payload["name"],
                address=payload.get(CONF_ADDRESS),
                boot_options=payload.get("boot_options") or [],
                broadcast_address=payload.get(CONF_BROADCAST_ADDRESS),
                broadcast_port=payload.get(CONF_BROADCAST_PORT),
            )

            LOGGER.info(
                "Discovered new host: %s (%s)",
                self.hosts[mac_address].name,
                mac_address,
            )
        else:
            old_name = self.hosts[mac_address].name

            self.hosts[mac_address].update_from_payload(payload)

            # Update the HA device registry so the entity name updates in the UI
            if old_name != self.hosts[mac_address].name:
                LOGGER.info(
                    "Host renamed: %s -> %s (%s)",
                    old_name,
                    self.hosts[mac_address].name,
                    mac_address,
                )
                device_reg = dr.async_get(self.hass)
                device = device_reg.async_get_device(
                    identifiers={(DOMAIN, mac_address)}
                )
                if device:
                    device_reg.async_update_device(
                        device.id, name=self.hosts[mac_address].name
                    )
            else:
                LOGGER.info(
                    "Received update for host: %s (%s) - boot options: %s",
                    self.hosts[mac_address].name,
                    mac_address,
                    self.hosts[mac_address].boot_options,
                )

        # add "(none)" option to the front of the list if it's not already there
        current_options = self.hosts[mac_address].boot_options
        if not current_options:
            boot_options = [DEFAULT_BOOT_OPTION_NONE]
        elif current_options[0] != DEFAULT_BOOT_OPTION_NONE:
            boot_options = [DEFAULT_BOOT_OPTION_NONE, *current_options]
        else:
            # It's already in the correct format
            boot_options = current_options

        self.hosts[mac_address].boot_options = boot_options

        # If the selected boot option is no longer in the list, reset it
        if (
            self.hosts[mac_address].next_boot_option not in boot_options
            and self.hosts[mac_address].next_boot_option != DEFAULT_BOOT_OPTION_NONE
        ):
            # Prevent boot-loops into non-existent OSes if the host's reported
            # options changed (e.g., OS uninstalled).
            self.hosts[mac_address].next_boot_option = DEFAULT_BOOT_OPTION_NONE

        if is_new_host:
            async_dispatcher_send(self.hass, SIGNAL_NEW_HOST, mac_address)
        else:
            async_dispatcher_send(self.hass, f"{DOMAIN}_update_{mac_address}")

        self.save()

    @callback
    def async_set_next_boot_option(
        self, mac_address: str, next_boot_option: str
    ) -> None:
        """Notify listeners that the selected boot option has changed."""
        mac_address = format_mac(mac_address)
        if mac_address in self.hosts:
            self.hosts[mac_address].next_boot_option = next_boot_option
            self.save()
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
        if mac_address not in self.hosts:
            LOGGER.warning(
                "GRUB requested boot option for unknown MAC address: %s", mac_address
            )
            return DEFAULT_BOOT_OPTION_NONE

        # grab the selected boot option and reset the state for next boot to
        # prevent boot loops
        next_boot_option = self.hosts[mac_address].next_boot_option
        self.hosts[mac_address].next_boot_option = DEFAULT_BOOT_OPTION_NONE
        self.save()

        # Notify UI to revert the dropdown back to "(none)"
        async_dispatcher_send(self.hass, f"{DOMAIN}_update_{mac_address}")

        return next_boot_option
