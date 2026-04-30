"""Tests for remote_boot_manager __init__.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.remote_boot_manager import (
    async_reload_entry,
    async_remove_config_entry_device,
    async_remove_entry,
)
from custom_components.remote_boot_manager.const import DOMAIN


async def test_async_remove_entry_with_runtime_data(hass):
    """Test async_remove_entry when the integration is loaded."""
    mock_entry = MagicMock()
    mock_manager = MagicMock()
    mock_manager.async_purge_data = AsyncMock()
    mock_entry.runtime_data = mock_manager

    await async_remove_entry(hass, mock_entry)

    mock_manager.async_purge_data.assert_awaited_once()


async def test_async_remove_entry_without_runtime_data(hass):
    """Test async_remove_entry when the integration is unloaded."""
    mock_entry = MagicMock()
    del mock_entry.runtime_data  # Ensure hasattr returns False

    with patch("custom_components.remote_boot_manager.Store") as mock_store_class:
        mock_store_instance = AsyncMock()
        mock_store_class.return_value = mock_store_instance

        await async_remove_entry(hass, mock_entry)

        mock_store_class.assert_called_once_with(hass, 1, f"{DOMAIN}.servers")
        mock_store_instance.async_remove.assert_awaited_once()


async def test_async_reload_entry(hass):
    """Test that async_reload_entry calls the underlying reload function."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await async_reload_entry(hass, mock_entry)
        mock_reload.assert_awaited_once_with("test_entry_id")


async def test_async_remove_config_entry_device(hass):
    """Test that removing a device also removes the server from the manager."""
    mock_manager = MagicMock()
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_manager

    mock_device_entry = MagicMock()
    mock_device_entry.identifiers = {(DOMAIN, "00:11:22:33:44:55")}

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, mock_device_entry
    )

    assert result is True
    mock_manager.async_remove_server.assert_called_once_with("00:11:22:33:44:55")


async def test_async_remove_config_entry_device_no_match(hass):
    """Test that removing a device with no matching identifier does nothing."""
    mock_manager = MagicMock()
    mock_config_entry = MagicMock()
    mock_config_entry.runtime_data = mock_manager

    mock_device_entry = MagicMock()
    mock_device_entry.identifiers = {("other_domain", "some_id")}

    result = await async_remove_config_entry_device(
        hass, mock_config_entry, mock_device_entry
    )

    assert result is True
    mock_manager.async_remove_server.assert_not_called()
