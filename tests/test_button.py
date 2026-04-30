"""Tests for Remote Boot Manager button."""

from unittest.mock import MagicMock, patch

from custom_components.remote_boot_manager.button import (
    RemoteBootManagerButton,
    async_setup_entry,
)
from custom_components.remote_boot_manager.manager import RemoteServer


async def test_async_setup_entry(hass):
    """Test the setup entry logic, including the dispatcher connection."""
    mock_entry = MagicMock()
    mock_manager = MagicMock()
    mock_manager.servers = {"00:11:22:33:44:55": MagicMock()}
    mock_entry.runtime_data = mock_manager
    async_add_entities = MagicMock()

    with patch(
        "custom_components.remote_boot_manager.button.async_dispatcher_connect"
    ) as mock_connect:
        await async_setup_entry(hass, mock_entry, async_add_entities)

        assert async_add_entities.call_count == 1
        mock_connect.assert_called_once()
        mock_entry.async_on_unload.assert_called_once()

        # Verify the dispatcher callback adds the new entity
        callback = mock_connect.call_args[0][2]
        mock_manager.servers["AA:BB:CC:DD:EE:FF"] = MagicMock()
        callback("AA:BB:CC:DD:EE:FF")
        assert async_add_entities.call_count == 2


async def test_button_async_press(hass):
    """Test button async_press sends packet."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            broadcast_address="192.168.1.255",
            broadcast_port=9,
        )
    }

    button = RemoteBootManagerButton(manager, "00:11:22:33:44:55")
    button.hass = hass

    with patch(
        "custom_components.remote_boot_manager.button.wakeonlan.send_magic_packet"
    ) as mock_send:
        await button.async_press()
        mock_send.assert_called_once_with(
            "00:11:22:33:44:55", ip_address="192.168.1.255", port=9
        )
