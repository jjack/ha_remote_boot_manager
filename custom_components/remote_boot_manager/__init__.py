"""
Custom integration to integrate remote_boot_manager with Home Assistant.

For more details about this integration, please refer to
https://github.com/jjack/ha_remote_boot_manager
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.const import Platform

from .const import DOMAIN, LOGGER, WEBHOOK_ID, WEBHOOK_NAME
from .manager import RemoteBootManager
from .views import BootloaderView

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import RemoteBootManagerConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    manager = RemoteBootManager(hass)
    entry.runtime_data = manager

    # register a webhook at /api/webhook/remote_boot_manager_ingest
    webhook.async_register(
        hass,
        DOMAIN,
        WEBHOOK_NAME,
        WEBHOOK_ID,
        handle_os_ingest_webhook,
    )
    # Register the unauthenticated bootloader view API
    hass.http.register_view(BootloaderView(manager))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    webhook.async_unregister(hass, WEBHOOK_ID)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def handle_os_ingest_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming OS push requests from bare-metal Go agents."""
    try:
        body = await request.text()
        if not body:
            LOGGER.warning(
                "Ignoring remote boot manager push request webhook with empty body"
            )
            return web.Response(status=400, text="empty body")

        payload = await request.json()
        LOGGER.debug("Received remote boot manager webhook with payload: %s", payload)
        mac_address = payload.get("mac_address")

        if not mac_address:
            LOGGER.warning(
                "Received remote boot manager push request webhook with no mac_address"
            )
            return web.Response(status=400, text="missing mac_address")

        # Find our manager instance from the active config entries
        for entry in hass.config_entries.async_entries(DOMAIN):
            LOGGER.debug(
                "Checking config entry %s for webhook payload processing",
                entry.entry_id,
            )
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                entry.runtime_data.async_process_webhook_payload(mac_address, payload)
                break

        return web.Response(status=200, text="OK")
    except Exception as err:
        LOGGER.error("Failed to process remote boot manager webhook: %s", err)
        return web.Response(status=500, text="Internal Server Error")
