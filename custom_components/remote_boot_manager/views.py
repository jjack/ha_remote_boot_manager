"""Views for the remote_boot_manager custom component."""

from __future__ import annotations

import dataclasses
import hmac
import logging
from http import HTTPStatus

from aiohttp import web
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.http import HomeAssistantView

from .bootloaders import async_get_bootloader
from .const import BOOTLOADER_VIEW_URL, DOMAIN

LOGGER = logging.getLogger(__name__)


class BootloaderView(HomeAssistantView):
    """View to handle unauthenticated bootloader requests."""

    # {mac_address} matches the `mac_address` argument to the get method
    url = BOOTLOADER_VIEW_URL
    name = f"api:{DOMAIN}:bootloader"
    requires_auth = False

    async def get(self, request: web.Request, mac_address: str) -> web.Response:
        """
        Handle GET requests for a specific host's boot configuration.

        By default, this endpoint is read-only.
        If a valid `token` (the integration's webhook ID) is provided in the query
        string, this endpoint deviates from RESTful principles by containing a
        side-effect: it "consumes" the next_boot_option and resets it to none.

        This is a necessary compromise because many basic bootloaders (e.g., GRUB)
        only support downloading configurations via HTTP GET and lack the capability
        to execute POST requests to acknowledge receipt.
        """
        hass = request.app["hass"]
        mac_address = format_mac(mac_address)

        error_msg = None
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        entries = None
        manager = None
        host = None
        bootloader = None

        if not mac_address:
            error_msg, status = "Invalid MAC address format", HTTPStatus.BAD_REQUEST
        elif not (entries := hass.config_entries.async_entries(DOMAIN)):
            error_msg = "Integration not configured"
        elif not (manager := entries[0].runtime_data):
            error_msg = "Integration not ready"
        elif not (host := manager.hosts.get(mac_address)):
            LOGGER.warning(
                "Bootloader request for unknown MAC address: %s", mac_address
            )
            error_msg, status = "Host not found", HTTPStatus.NOT_FOUND
        elif not (bootloader_name := host.bootloader):
            LOGGER.error("No bootloader configured for %s", mac_address)
            error_msg, status = (
                "No bootloader configured for this host",
                HTTPStatus.BAD_REQUEST,
            )
        elif not (bootloader := await async_get_bootloader(hass, bootloader_name)):
            LOGGER.error(
                "Bootloader module %s not found for %s", bootloader_name, mac_address
            )
            error_msg, status = "Bootloader not supported", HTTPStatus.BAD_REQUEST

        if error_msg or not bootloader or not host or not manager or not entries:
            return web.json_response(
                {"error": error_msg or "Internal Server Error"}, status=status
            )

        # Call the appropriate bootloader instance to generate the response and (maybe)
        # consume the next boot option.
        try:
            token = request.query.get("token")
            valid_token = str(entries[0].data.get("webhook_id", ""))

            # Authenticated GET requests with a valid token intentionally mutate state
            # by "consuming" the boot option to prevent infinite boot loops.
            host_copy = dataclasses.asdict(host)
            if token and valid_token and hmac.compare_digest(token, valid_token):
                host_copy["next_boot_option"] = manager.async_consume_next_boot_option(
                    mac_address
                )
            else:
                host_copy["next_boot_option"] = host.next_boot_option

            return bootloader.generate_boot_config(host_copy)
        except Exception:
            LOGGER.exception("Error generating boot config for %s", mac_address)
            return web.json_response(
                {"error": "Internal Server Error"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
