"""Webhook handlers for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import web
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
)
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_BOOT_OPTIONS,
    CONF_BOOTLOADER,
    DOMAIN,
    LOGGER,
    WEBHOOK_MAX_PAYLOAD_BYTES,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): format_mac,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_BOOTLOADER): cv.string,
        vol.Optional(CONF_BOOT_OPTIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
    }
)


async def async_validate_webhook_payload(
    request: web.Request,
) -> tuple[dict[str, Any] | None, web.Response | None]:
    """Validate and parse incoming webhook payload."""
    body = await request.text()
    if not body:
        LOGGER.warning(
            "Ignoring remote boot manager push request webhook with empty body"
        )
        return None, web.Response(status=400, text="empty body")

    if len(body) > WEBHOOK_MAX_PAYLOAD_BYTES:
        LOGGER.warning("Webhook payload too large")
        return None, web.Response(status=413, text="Payload too large")

    try:
        raw_payload = await request.json()
    except ValueError:
        LOGGER.warning("Webhook payload is not valid JSON")
        LOGGER.debug("Received invalid JSON payload: %s", body)
        return None, web.Response(status=400, text="Invalid JSON payload")

    LOGGER.debug("Received remote boot manager webhook with payload: %s", raw_payload)

    try:
        # Use cast to force the type checker to treat the output as a dict
        payload = cast("dict[str, Any]", WEBHOOK_SCHEMA(raw_payload))
    except vol.Invalid as err:
        LOGGER.warning("Invalid webhook schema from incoming request: %s", err)
        return None, web.Response(status=400, text=f"Invalid payload format: {err}")

    return payload, None


async def handle_boot_options_ingest_webhook(
    hass: HomeAssistant, _webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming boot options push requests from bare-metal Go agents."""
    try:
        payload, error_response = await async_validate_webhook_payload(request)
        if error_response:
            return error_response

        if payload is None:
            return web.Response(status=500, text="Unexpected empty payload")

        # Find our manager instance from the active config entries
        manager_found = False
        mac_address = payload.get(CONF_MAC)
        for entry in hass.config_entries.async_entries(DOMAIN):
            LOGGER.debug(
                "Checking config entry %s for webhook payload processing",
                entry.entry_id,
            )
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                entry.runtime_data.async_process_webhook_payload(mac_address, payload)
                manager_found = True
                break

        if not manager_found:
            return web.Response(status=503, text="Integration not ready")

        return web.Response(status=200, text="OK")
    except Exception as err:  # noqa: BLE001
        LOGGER.error("Failed to process webhook: %s", err)
        return web.Response(status=500, text="Internal Server Error")
