# ruff: noqa: S101
"""Test manager for remote_boot_manager."""
from unittest.mock import patch, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.const import DOMAIN, DEFAULT_OS_NONE
from custom_components.remote_boot_manager.manager import RemoteBootManager

async def test_manager_load_with_data(hass: HomeAssistant) -> None:
    """Test loading manager with existing store data."""
    manager = RemoteBootManager(hass)
    with patch("homeassistant.helpers.storage.Store.async_load", return_value={"servers": {"aa:bb:cc": {}}}):
        await manager.async_load()
        assert "aa:bb:cc" in manager.servers

async def test_manager_remove_server(hass: HomeAssistant) -> None:
    """Test removing a server."""
    manager = RemoteBootManager(hass)
    manager.servers["aa:bb:cc"] = {}
    manager.async_remove_server("aa:bb") # unknown
    assert "aa:bb:cc" in manager.servers
    manager.async_remove_server("aa:bb:cc") # known
    assert "aa:bb:cc" not in manager.servers

@pytest.fixture
def mock_manager(hass: HomeAssistant) -> RemoteBootManager:
    return RemoteBootManager(hass)

async def test_manager_process_existing_server(hass: HomeAssistant, mock_manager: RemoteBootManager) -> None:
    """Test updating existing server info."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    dev_reg = async_get_dr(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")},
        name="old-name"
    )

    mock_manager.servers["aa:bb:cc:dd:ee:ff"] = {
        "hostname": "old-name",
        "selected_os": "ubuntu",
        "os_list": ["(none)", "ubuntu", "windows"],
        "bootloader": "grub"
    }

    # Call with new hostname
    payload = {
        "hostname": "new-name",
        "os_list": ["windows"], # ubuntu removed
        "bootloader": "grub"
    }
    
    mock_manager._notify_listeners = MagicMock()
    mock_manager.async_process_webhook_payload("aa:bb:cc:dd:ee:ff", payload)

    assert mock_manager.servers["aa:bb:cc:dd:ee:ff"]["hostname"] == "new-name"
    # selected_os should have been reset to default because "ubuntu" is not in ["windows"]
    assert mock_manager.servers["aa:bb:cc:dd:ee:ff"]["selected_os"] == DEFAULT_OS_NONE
    mock_manager._notify_listeners.assert_called_once()

    # check device name updated
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")})
    assert device.name == "new-name"

async def test_manager_consume_unknown_mac(hass: HomeAssistant, mock_manager: RemoteBootManager) -> None:
    """Test consuming from an unknown MAC returns default."""
    assert mock_manager.async_consume_selected_os("unknown") == DEFAULT_OS_NONE

async def test_manager_existing_server_no_device(hass: HomeAssistant, mock_manager: RemoteBootManager) -> None:
    """Test updating an existing server when the device is not found."""
    mock_manager.servers["aa:bb:cc"] = {
        "hostname": "old-name",
        "selected_os": "foo",
        "os_list": ["foo"],
        "bootloader": "grub"
    }
    payload = {
        "hostname": "new-name",
        "os_list": ["foo"],
        "bootloader": "grub"
    }
    # No device exists in DR
    mock_manager.async_process_webhook_payload("aa:bb:cc", payload)
    assert mock_manager.servers["aa:bb:cc"]["hostname"] == "new-name"

