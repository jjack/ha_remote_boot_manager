"""Views for the remote_boot_manager custom component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.http import HomeAssistantView

from .bootloaders import get_bootloader
from .const import BOOTLOADER_VIEW_URL, DOMAIN

if TYPE_CHECKING:
    from .manager import RemoteBootManager


LOGGER = logging.getLogger(__name__)


class BootloaderView(HomeAssistantView):
    """View to handle unauthenticated bootloader requests."""

    # {mac_address} matches the `mac_address` argument to the get method
    url = BOOTLOADER_VIEW_URL
    name = f"api:{DOMAIN}:bootloader"
    requires_auth = False

    def __init__(self) -> None:
        """Initialize."""
        pass

    async def get(self, request: web.Request, mac_address: str) -> web.Response:
        """Handle GET requests for a specific server's boot configuration."""
        hass = request.app["hass"]
        mac_address = format_mac(mac_address)

        # Find our manager instance from the active config entries
        manager = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                manager = entry.runtime_data
                break

        if not manager:
            return web.json_response({"error": "Integration not ready"}, status=503)

        server = manager.servers.get(mac_address, {})

        if not server:
            LOGGER.warning(
                "Bootloader request for unknown MAC address: %s", mac_address
            )
            return web.json_response({"error": "Server not found"}, status=404)

        bootloader_name = server.get("bootloader", "")
        bootloader = get_bootloader(bootloader_name)
        if not bootloader:
            LOGGER.error(
                "Bootloader module %s not found for %s", bootloader_name, mac_address
            )
            return web.json_response({"error": "Bootloader not supported"}, status=400)

        # Call the appropriate bootloader instance to generate the response
        try:
            server_copy = server.copy()
            server_copy["selected_os"] = manager.async_consume_selected_os(mac_address)
            return bootloader.generate_boot_config(server_copy)
        except Exception as err:
            LOGGER.error("Error generating boot config for %s: %s", mac_address, err)
            return web.json_response({"error": "Internal Server Error"}, status=500)
