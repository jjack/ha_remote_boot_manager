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

from .const import DOMAIN, LOGGER

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
    webook_id: str,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    # register a webhook at /api/webhook/remote_boot_manager_ingest
    webhook.async_register(
        hass,
        DOMAIN,
        "Remote Boot Manager Ingest",
        "remote_boot_manager_ingest",
        handle_os_ingest_webhook,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> bool:
    """Handle removal of an entry."""
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
        payload = await request.json()
        mac_address = payload.get("mac_address")

        if not mac_address:
            LOGGER.warning(
                "Received remote boot manager push request webhook with no mac_address"
            )
            return web.Response(status=400, text="missing mac_address")

        # Find our manager instance from the active config entries
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                entry.runtime_data.async_process_webhook_payload(mac_address, payload)
                break

        return web.Response(status=200, text="OK")

    except Exception as err:
        LOGGER.error("Failed to process remote boot manager webhook: %s", err)
        return web.Response(status=400, text="Invalid JSON Payload")
