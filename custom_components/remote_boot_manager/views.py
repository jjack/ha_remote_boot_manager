"""Views for the remote_boot_manager custom component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import web
from homeassistant.helpers.http import HomeAssistantView

from .bootloaders import get_bootloader
from .const import DOMAIN

if TYPE_CHECKING:
    from .manager import RemoteBootManager


LOGGER = logging.getLogger(__name__)


class BootloaderView(HomeAssistantView):
    """View to handle unauthenticated bootloader requests."""

    # {mac_address} matches the `mac_address` argument to the get method
    url = "/api/remote_boot_manager/{mac_address}"
    name = f"api:{DOMAIN}:bootloader"
    requires_auth = False

    def __init__(self, manager: RemoteBootManager) -> None:
        """Initialize."""
        self.manager = manager

    async def get(self, request: web.Request, mac_address: str) -> web.Response:
        """Handle GET requests for a specific server's boot configuration."""
        server = self.manager.servers.get(mac_address, {})

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
            return bootloader.generate_boot_config(self.manager.servers[mac_address])
        except Exception as err:
            LOGGER.error("Error generating boot config for %s: %s", mac_address, err)
            return web.json_response({"error": "Internal Server Error"}, status=500)
