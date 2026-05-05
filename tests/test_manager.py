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
        mock_instance = MagicMock()
        mock_instance.async_load = AsyncMock(return_value={})
        mock_instance.async_remove = AsyncMock()
        mock_store_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def manager(hass, mock_store):
    """Fixture for providing a clean RemoteBootManager."""
    return RemoteBootManager(hass)


async def test_async_process_webhook_payload_new_server(manager, hass):
    """Test that a new server is added correctly from a payload."""
    payload = {
        "name": "test-server",
        "host": "192.168.1.100",
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
        assert server.name == "test-server"
        assert server.host == "192.168.1.100"
        # make sure that (none) is prepended
        assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "windows"]

        mock_dispatch.assert_called_once()


async def test_async_process_webhook_payload_none_option_already_present(manager, hass):
    """Test that the default none boot option is not duplicated if already present."""
    payload = {
        "name": "test-server",
        "host": "192.168.1.100",
        "bootloader": "grub",
        "boot_options": [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "windows"],
    }

    manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

    server = manager.servers["00:11:22:33:44:55"]
    assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "windows"]


async def test_async_process_webhook_payload_update_existing_server(manager, hass):
    """Test that an existing server is updated correctly, including device registry rename."""
    # Setup existing server
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="old-hostname",
        bootloader="grub",
        boot_options=["ubuntu"],
    )

    payload = {
        "name": "new-hostname",
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
        assert server.name == "new-hostname"
        assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "arch"]

        # Verify device registry was updated with the new hostname
        mock_registry.async_update_device.assert_called_once_with(
            "device_123", name="new-hostname"
        )


async def test_async_set_and_consume_next_boot_option(manager, hass):
    """Test setting and safely consuming the next boot option."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="test-server",
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


async def test_async_remove_server_invalid_mac(manager, hass):
    """Test removing a non-existent server does nothing."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="test-server",
    )
    with patch.object(manager, "_save") as mock_save:
        manager.async_remove_server("FF:FF:FF:FF:FF:FF")
        assert "00:11:22:33:44:55" in manager.servers
        mock_save.assert_not_called()


async def test_async_load_no_data(manager, mock_store):
    """Test loading from an empty or non-existent store."""
    mock_store.async_load.return_value = None
    await manager.async_load()
    assert manager.servers == {}

    mock_store.async_load.return_value = {"other_key": "other_value"}
    await manager.async_load()
    assert manager.servers == {}


async def test_async_load_valid_data(manager, mock_store):
    """Test loading valid server data from storage."""
    mock_store.async_load.return_value = {
        "servers": {
            "00:11:22:33:44:55": {
                "mac": "00:11:22:33:44:55",
                "name": "Stored Server",
                "host": "192.168.1.50",
            }
        }
    }
    await manager.async_load()

    assert "00:11:22:33:44:55" in manager.servers
    server = manager.servers["00:11:22:33:44:55"]
    assert server.name == "Stored Server"
    assert server.host == "192.168.1.50"


async def test_async_load_invalid_data_format(manager, mock_store):
    """Test loading invalid server data format logs a warning and skips it."""
    mock_store.async_load.return_value = {
        "servers": {"00:11:22:33:44:55": ["list", "instead", "of", "dict"]}
    }

    with patch(
        "custom_components.remote_boot_manager.manager.LOGGER.warning"
    ) as mock_warn:
        await manager.async_load()

    assert "00:11:22:33:44:55" not in manager.servers
    mock_warn.assert_called_once()
    assert "Discarding invalid server data" in mock_warn.call_args[0][0]


async def test_async_load_filters_extra_keys(manager, mock_store):
    """Test loading data with unknown keys correctly filters them out."""
    mock_store.async_load.return_value = {
        "servers": {
            "00:11:22:33:44:55": {
                "mac": "00:11:22:33:44:55",
                "name": "Filtered Server",
                "unknown_future_key": "some_value",
            }
        }
    }

    await manager.async_load()

    assert "00:11:22:33:44:55" in manager.servers
    server = manager.servers["00:11:22:33:44:55"]
    assert server.name == "Filtered Server"
    assert not hasattr(server, "unknown_future_key")


async def test_async_purge_data(manager, mock_store):
    """Test that purging data clears servers and removes the store file."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55", name="test"
    )
    await manager.async_purge_data()
    assert not manager.servers
    mock_store.async_remove.assert_awaited_once()


async def test_async_process_webhook_payload_update_no_rename(manager, hass):
    """Test that an existing server is updated without renaming the device."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="same-hostname",
        bootloader="grub",
        boot_options=["ubuntu"],
    )

    payload = {
        "name": "same-hostname",  # name is the same
        "bootloader": "refind",  # bootloader changed
        "boot_options": ["ubuntu", "arch"],
    }

    with patch("custom_components.remote_boot_manager.manager.dr.async_get") as mock_dr:
        mock_registry = MagicMock()
        mock_dr.return_value = mock_registry

        manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

        server = manager.servers["00:11:22:33:44:55"]
        assert server.bootloader == "refind"
        assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "arch"]

        # Verify device registry was NOT updated
        mock_registry.async_update_device.assert_not_called()


async def test_async_process_webhook_payload_update_device_not_found(manager, hass):
    """Test that an update with a rename does not fail if the device is not found."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="old-hostname",
    )
    payload = {"name": "new-hostname"}

    with patch("custom_components.remote_boot_manager.manager.dr.async_get") as mock_dr:
        mock_registry = MagicMock()
        mock_dr.return_value = mock_registry
        mock_registry.async_get_device.return_value = None  # Device not found

        manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

        server = manager.servers["00:11:22:33:44:55"]
        assert server.name == "new-hostname"
        mock_registry.async_update_device.assert_not_called()


async def test_async_process_webhook_payload_resets_invalid_next_boot(manager, hass):
    """Test that next_boot_option is reset if it becomes invalid after an update."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="test-server",
        boot_options=["ubuntu", "windows"],
        next_boot_option="windows",  # This will become invalid
    )
    payload = {"name": "test-server", "boot_options": ["ubuntu", "fedora"]}

    manager.async_process_webhook_payload("00:11:22:33:44:55", payload)

    server = manager.servers["00:11:22:33:44:55"]
    assert server.boot_options == [DEFAULT_BOOT_OPTION_NONE, "ubuntu", "fedora"]
    assert server.next_boot_option == DEFAULT_BOOT_OPTION_NONE


async def test_async_set_next_boot_option_invalid_mac(manager, hass):
    """Test setting a boot option for a non-existent MAC does nothing."""
    with patch(
        "custom_components.remote_boot_manager.manager.async_dispatcher_send"
    ) as mock_dispatch:
        manager.async_set_next_boot_option("FF:FF:FF:FF:FF:FF", "windows")
        assert "FF:FF:FF:FF:FF:FF" not in manager.servers
        mock_dispatch.assert_not_called()


async def test_async_consume_next_boot_option_invalid_mac(manager, hass):
    """Test consuming a boot option for a non-existent MAC returns default."""
    consumed = manager.async_consume_next_boot_option("FF:FF:FF:FF:FF:FF")
    assert consumed == DEFAULT_BOOT_OPTION_NONE


async def test_async_remove_server(manager, hass):
    """Test removing a server from the manager."""
    manager.servers["00:11:22:33:44:55"] = RemoteServer(
        mac="00:11:22:33:44:55",
        name="test-server",
        bootloader="grub",
    )

    manager.async_remove_server("00:11:22:33:44:55")
    assert "00:11:22:33:44:55" not in manager.servers
