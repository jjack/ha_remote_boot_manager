"""
Custom integration to integrate remote_boot_manager with Home Assistant.

For more details about this integration, please refer to
https://github.com/jjack/ha_remote_boot_manager
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiohttp import web
from homeassistant.components import webhook
from homeassistant.const import CONF_MAC, Platform
from homeassistant.helpers.device_registry import DeviceEntry, format_mac

from .const import DOMAIN, LOGGER, WEBHOOK_MAX_PAYLOAD_BYTES, WEBHOOK_NAME
from .manager import RemoteBootManager
from .views import BootloaderView

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import RemoteBootManagerConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
]


def coerce_mac_address(value: str) -> str:
    """Ensure a string is a valid, formatted MAC address."""
    raw_mac = cv.string(value)
    formatted_mac = format_mac(raw_mac)

    if formatted_mac is None:
        err_msg = f"'{value}' is not a valid MAC address format"
        raise vol.Invalid(err_msg)

    return formatted_mac


WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): coerce_mac_address,
        vol.Optional("hostname", default="Unknown Server"): cv.string,
        vol.Optional("bootloader", default="unknown"): cv.string,
        vol.Optional("os_list", default=[]): vol.All(cv.ensure_list, [cv.string]),
    },
    extra=vol.ALLOW_EXTRA,
)


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:  # noqa: ARG001
    """Set up the remote_boot_manager component."""
    # Register the unauthenticated bootloader view API
    hass.http.register_view(BootloaderView())

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
        webhook.async_register(
            hass,
            DOMAIN,
            WEBHOOK_NAME,
            webhook_id,
            handle_os_ingest_webhook,
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
        webhook.async_unregister(hass, webhook_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


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


async def handle_os_ingest_webhook(
    hass: HomeAssistant, _webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming OS push requests from bare-metal Go agents."""
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
        manager = RemoteBootManager(hass)
        await manager.async_purge_data()


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
