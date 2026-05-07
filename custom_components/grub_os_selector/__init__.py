"""
Custom integration to integrate grub_os_selector with Home Assistant.

For more details about this integration, please refer to
https://github.com/jjack/ha-grub-os-selector
"""

from __future__ import annotations

from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import wakeonlan
from aiohttp import web
from homeassistant.components import webhook as ha_webhook
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_MAC,
    Platform,
)
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LOGGER, WEBHOOK_NAME
from .manager import GrubOSSelectManager
from .views import GrubConfigView
from .webhook import async_validate_webhook_payload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.device_registry import DeviceEntry

    from .data import GrubOSSelectManagerConfigEntry

SERVICE_SEND_MAGIC_PACKET = "send_magic_packet"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
    }
)

PLATFORMS: list[Platform] = [
    Platform.SELECT,
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:  # noqa: ARG001
    """Set up the grub_os_selector component."""

    async def send_magic_packet(call: ServiceCall) -> None:
        """Send magic packet to wake up a device."""
        mac_address = call.data[CONF_MAC]
        kwargs = {}
        if CONF_BROADCAST_ADDRESS in call.data:
            kwargs["ip_address"] = call.data[CONF_BROADCAST_ADDRESS]
        if CONF_BROADCAST_PORT in call.data:
            kwargs["port"] = call.data[CONF_BROADCAST_PORT]

        # wakeonlan uses blocking sockets; offload to an executor thread to prevent
        # stalling the HA event loop.
        await hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, mac_address, **kwargs)
        )

    # Register the send_magic_packet service to duplicate the functionality of the
    # built-in Wake on LAN integration so this can be called directly from
    # automations, scripts, or other integrations.
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MAGIC_PACKET,
        send_magic_packet,
        schema=WAKE_ON_LAN_SEND_MAGIC_PACKET_SCHEMA,
    )

    # Register the unauthenticated GRUB get request view
    # (ie - GET /api/grub_os_selector/{mac_address})   # noqa: ERA001
    hass.http.register_view(GrubConfigView())

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrubOSSelectManagerConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    manager = GrubOSSelectManager(hass)
    await manager.async_load()
    entry.runtime_data = manager

    async def handle_webhook(
        hass: HomeAssistant,  # noqa: ARG001
        webhook_id: str,  # noqa: ARG001
        request: web.Request,
    ) -> web.Response:
        """Handle incoming boot option push requests."""
        try:
            LOGGER.debug("received webhook request: %s", request)
            payload, error_response = await async_validate_webhook_payload(request)
            if error_response:
                return error_response
            if payload is None:
                return web.Response(
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                    text="Unexpected empty payload",
                )
            if CONF_MAC not in payload:
                return web.Response(
                    status=HTTPStatus.BAD_REQUEST,
                    text="MAC address missing from payload",
                )

            manager.async_process_webhook_payload(payload[CONF_MAC], payload)
            return web.Response(status=HTTPStatus.OK, text="OK")
        except Exception:  # noqa: BLE001
            return web.Response(
                status=HTTPStatus.INTERNAL_SERVER_ERROR, text="Internal Server Error"
            )

    # Register the webhook to receive the boot options push requests
    webhook_id = entry.data.get("webhook_id")
    if webhook_id:
        ha_webhook.async_register(
            hass,
            DOMAIN,
            WEBHOOK_NAME,
            webhook_id,
            handle_webhook,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GrubOSSelectManagerConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    webhook_id = entry.data.get("webhook_id")
    if webhook_id:
        ha_webhook.async_unregister(hass, webhook_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: GrubOSSelectManagerConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: GrubOSSelectManagerConfigEntry,
) -> None:
    """Handle removal of an entry."""
    # Since async_unload_entry unregisters the webhook and Home Assistant automatically
    # handles device/entity removal, we just need to purge the manager data.
    if hasattr(entry, "runtime_data") and entry.runtime_data:
        await entry.runtime_data.async_purge_data()
    else:
        # Fallback if entry was never loaded
        await Store(hass, 1, f"{DOMAIN}.hosts").async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: GrubOSSelectManagerConfigEntry,
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

    # Remove the host from our internal state
    if mac_address:
        manager.async_remove_host(mac_address)

    return True
