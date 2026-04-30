"""Tests for the RemoteBootManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.remote_boot_manager.const import DEFAULT_BOOT_OPTION_NONE
from custom_components.remote_boot_manager.manager import (
    RemoteBootManager,
    RemoteServer,
)


@pytest.fixture
def mock_store():
    """Mock the HA Store implementation."""
    with patch(
        "custom_components.remote_boot_manager.manager.Store"
    ) as mock_store_class:
        mock_instance = AsyncMock()
        mock_store_class.return_value = mock_instance
        mock_instance.async_load.return_value = {}
        yield mock_instance


@pytest.fixture
def manager(hass, mock_store):
    """Fixture for providing a clean RemoteBootManager."""
    return RemoteBootManager(hass)


async def test_async_process_webhook_payload_new_server(manager, hass):
    """Test that a new server is added correctly from a payload."""
    payload = {
        "hostname": "test-server",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "windows"],
    }

    with patch(
        "custom_components.remote_boot_manager.manager.async_dispatcher_send"
    ) as mock_dispatch:
        manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

        assert "00:11:22:33:44:55" in manager.servers
        server = manager.servers["00:11:22:33:44:55"]
        assert isinstance(server, RemoteServer)
        assert server.hostname == "test-server"
        # make sure that (none) is prepended
        assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "windows"]

        mock_dispatch.assert_called_once()


async def test_async_process_webhook_payload_update_existing_server(manager, hass):
    """Test that an existing server is updated correctly, including device registry rename."""
    # Setup existing server
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        hostname="old-hostname",
        bootloader="grub",
        boot_options=["ubuntu"],
    )

    payload = {
        "hostname": "new-hostname",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "arch"],
    }

    with patch("custom_components.remote_boot_manager.manager.dr.async_get") as mock_dr:
        mock_registry = MagicMock()
        mock_dr.return_value = mock_registry
        mock_device = MagicMock()
        mock_device.id = "device_123"
        mock_registry.async_get_device.return_value = mock_device

        manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

        server = manager.servers["00:11:22:33:44:55"]
        assert server.hostname == "new-hostname"
        assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "arch"]

        # Verify device registry was updated with the new hostname
        mock_registry.async_update_device.assert_called_once_with(
            "device_123", name="new-hostname"
        )


async def test_async_set_and_consume_next_boot_option(manager, hass):
    """Test setting and safely consuming the next boot option."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        hostname="test-server",
        bootloader="grub",
        boot_options=[DEFAULT_BOOT_OPTION_NONE, "ubuntu", "windows"],
    )

    # Set the option
    manager.async_set_next_boot_option("00:11:22:33:44:55", "windows")
    assert manager.servers["00:11:22:33:44:55"].next_boot_option == "windows"

    # Consume the option (should return it, and reset state)
    consumed = manager.async_consume_next_boot_option("00:11:22:33:44:55")
    assert consumed == "windows"
    assert (
        manager.servers["00:11:22:33:44:55"].next_boot_option
        == DEFAULT_BOOT_OPTION_NONE
    )


async def test_async_remove_server(manager, hass):
    """Test removing a server from the manager."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        hostname="test-server",
        bootloader="grub",
    )

    manager.async_remove_server("00:11:22:33:44:55")
    assert "00:11:22:33:44:55" not in manager.servers
