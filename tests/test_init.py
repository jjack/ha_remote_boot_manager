"""Test __init__ for remote_boot_manager."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.__init__ import (
    async_reload_entry,
    async_remove_config_entry_device,
    async_remove_entry,
    async_validate_webhook_payload,
    coerce_mac_address,
    handle_os_ingest_webhook,
)
from custom_components.remote_boot_manager.const import (
    DOMAIN,
    WEBHOOK_MAX_PAYLOAD_BYTES,
)
from custom_components.remote_boot_manager.manager import RemoteBootManager


def test_coerce_mac_address() -> None:
    """Test MAC address coercion."""
    assert coerce_mac_address("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"


async def test_webhook_payload_validation(hass: HomeAssistant) -> None:
    """Test webhook payload edge cases."""
    # Test empty payload
    mock_request = MagicMock(spec=web.Request)
    mock_request.text.return_value = ""
    payload, err_response = await async_validate_webhook_payload(mock_request)
    assert payload is None
    assert err_response is not None
    assert err_response.status == 400

    # Test payload too large
    mock_request.text.return_value = "x" * (WEBHOOK_MAX_PAYLOAD_BYTES + 1)
    payload, err_response = await async_validate_webhook_payload(mock_request)
    assert payload is None
    assert err_response is not None
    assert err_response.status == 413

    # Test invalid JSON
    mock_request.text.return_value = "not json"
    mock_request.json.side_effect = ValueError()
    payload, err_response = await async_validate_webhook_payload(mock_request)
    assert payload is None
    assert err_response is not None
    assert err_response.status == 400

    # Test invalid schema (missing MAC)
    mock_request.text.return_value = '{"hostname": "test"}'
    mock_request.json.return_value = {"hostname": "test"}
    mock_request.json.side_effect = None
    payload, err_response = await async_validate_webhook_payload(mock_request)
    assert payload is None
    assert err_response is not None
    assert err_response.status == 400


async def test_handle_webhook_error_cases(hass: HomeAssistant) -> None:
    """Test handle webhook error responses."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.text.return_value = ""

    # Empty body triggers 400 immediately
    resp = await handle_os_ingest_webhook(hass, "test", mock_request)
    assert resp.status == 400

    # Exception inside triggers 500
    with patch(
        "custom_components.remote_boot_manager.__init__.async_validate_webhook_payload",
        side_effect=Exception("Boom"),
    ):
        resp = await handle_os_ingest_webhook(hass, "test", mock_request)
        assert resp.status == 500

    # Valid payload, but no manager found
    with patch(
        "custom_components.remote_boot_manager.__init__.async_validate_webhook_payload",
        return_value=({"mac": "aa:bb:cc:dd:ee:ff"}, None),
    ):
        resp = await handle_os_ingest_webhook(hass, "test", mock_request)
        assert resp.status == 503


async def test_manage_device_removal(hass: HomeAssistant) -> None:
    """Test device removal logic."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    manager = RemoteBootManager(hass)
    entry.runtime_data = manager

    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")}
    )

    manager.servers["aa:bb:cc:dd:ee:ff"] = {"mac": "aa:bb:cc:dd:ee:ff"}
    await async_remove_config_entry_device(hass, entry, device)
    assert "aa:bb:cc:dd:ee:ff" not in manager.servers


async def test_async_remove_entry_fallback(hass: HomeAssistant) -> None:
    """Test removing entry that lacks runtime_data."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    # no runtime_data
    with patch(
        "custom_components.remote_boot_manager.manager.RemoteBootManager.async_purge_data"
    ) as mock_purge:
        await async_remove_entry(hass, entry)
        mock_purge.assert_called_once()


async def test_async_reload_entry(hass: HomeAssistant) -> None:
    """Test config reload."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await async_reload_entry(hass, entry)
        mock_reload.assert_called_once_with(entry.entry_id)


def test_coerce_mac_address_invalid() -> None:
    """Test MAC address coercion."""
    with patch(
        "custom_components.remote_boot_manager.__init__.format_mac", return_value=None
    ), pytest.raises(vol.Invalid):
        coerce_mac_address("invalid")
