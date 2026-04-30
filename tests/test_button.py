"""Tests for Remote Boot Manager button."""

from unittest.mock import MagicMock, patch

from custom_components.remote_boot_manager.button import RemoteBootManagerButton
from custom_components.remote_boot_manager.manager import RemoteServer


async def test_button_async_press_no_broadcast_args(hass):
    """Test button async_press with no broadcast arguments."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            hostname="Test Server",
            bootloader="grub",
        )
    }

    button = RemoteBootManagerButton(manager, "00:11:22:33:44:55")
    button.hass = hass

    with patch(
        "custom_components.remote_boot_manager.button.wakeonlan.send_magic_packet"
    ) as mock_send:
        await button.async_press()
        await hass.async_block_till_done()

        mock_send.assert_called_once_with("00:11:22:33:44:55")


async def test_button_async_press_with_broadcast_args(hass):
    """Test button async_press with broadcast arguments."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            hostname="Test Server",
            bootloader="grub",
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
        await hass.async_block_till_done()

        mock_send.assert_called_once_with(
            "00:11:22:33:44:55", ip_address="192.168.1.255", port=9
        )
