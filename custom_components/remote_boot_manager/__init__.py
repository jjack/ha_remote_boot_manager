"""
Custom integration to integrate remote_boot_manager with Home Assistant.

For more details about this integration, please refer to
https://github.com/jjack/hass-remote-boot-manager
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import wakeonlan
from homeassistant.components import webhook as ha_webhook
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_MAC,
    Platform,
)
from homeassistant.helpers.storage import Store

from .const import DOMAIN, WEBHOOK_NAME
from .manager import RemoteBootManager
from .views import BootloaderView
from .webhook import handle_boot_options_ingest_webhook

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.device_registry import DeviceEntry

    from .data import RemoteBootManagerConfigEntry

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
    }
)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:  # noqa: ARG001
    """Set up the remote_boot_manager component."""
    # Register the unauthenticated bootloader view API
    hass.http.register_view(BootloaderView())

    async def send_magic_packet(call: ServiceCall) -> None:
        """Send magic packet to wake up a device."""
        mac_address = call.data[CONF_MAC]
        kwargs = {}
        if CONF_BROADCAST_ADDRESS in call.data:
            kwargs["ip_address"] = call.data[CONF_BROADCAST_ADDRESS]
        if CONF_BROADCAST_PORT in call.data:
            kwargs["port"] = call.data[CONF_BROADCAST_PORT]

        await hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, mac_address, **kwargs)
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    manager = RemoteBootManager(hass)
    await manager.async_load()
    entry.runtime_data = manager

    # Register the webhook globally since it iterates over all entries
    webhook_id = entry.data.get("webhook_id")
    if webhook_id:
        ha_webhook.async_register(
            hass,
            DOMAIN,
            WEBHOOK_NAME,
            webhook_id,
            handle_boot_options_ingest_webhook,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    webhook_id = entry.data.get("webhook_id")
    if webhook_id:
        ha_webhook.async_unregister(hass, webhook_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> None:
    """Handle removal of an entry."""
    # Since async_unload_entry unregisters the webhook,
    # and Home Assistant automatically handles device/entity removal,
    # we just need to purge the manager data.
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        await entry.runtime_data.async_purge_data()
    else:
        # Fallback if entry was never loaded
        await Store(hass, 1, f"{DOMAIN}.servers").async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: RemoteBootManagerConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Remove a device from a config entry and clean up manager data."""
    manager = config_entry.runtime_data

    # Extract the MAC address from the device's identifiers
    mac_address = next(
        (
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
        None,
    )

    # Remove the server from our internal state
    if mac_address:
        manager.async_remove_server(mac_address)

    return True
