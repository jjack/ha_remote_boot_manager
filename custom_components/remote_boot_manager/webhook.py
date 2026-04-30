"""Webhook handlers for remote_boot_manager."""

from __future__ import annotations

from typing import Any, cast

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
    LOGGER,
    WEBHOOK_MAX_PAYLOAD_BYTES,
)

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): format_mac,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_BOOTLOADER): cv.string,
        vol.Optional(CONF_BOOT_OPTIONS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_BROADCAST_ADDRESS): cv.string,
        vol.Optional(CONF_BROADCAST_PORT): cv.port,
        vol.Optional("entity_type", default="button"): vol.In(["button", "switch"]),
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
