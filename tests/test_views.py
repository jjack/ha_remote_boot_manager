"""Test views for remote_boot_manager."""

from unittest.mock import MagicMock, patch

from aiohttp import web
from homeassistant.core import HomeAssistant

from custom_components.remote_boot_manager.manager import RemoteServer
from custom_components.remote_boot_manager.views import BootloaderView


async def test_bootloader_view_invalid_mac(hass: HomeAssistant) -> None:
    """Test Invalid MAC."""
    mock_manager = MagicMock()
    view = BootloaderView(mock_manager)
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    with patch(
        "custom_components.remote_boot_manager.views.format_mac", return_value=None
    ):
        resp = await view.get(mock_request, "invalid")
        assert resp.status == 400


async def test_bootloader_view_server_not_found(hass: HomeAssistant) -> None:
    """Test server not found."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {}
    view = BootloaderView(mock_manager)

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == 404


async def test_bootloader_view_unsupported_bootloader(hass: HomeAssistant) -> None:
    """Test unsupported bootloader."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="unsupported",
        )
    }
    view = BootloaderView(mock_manager)

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=None,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 400


async def test_bootloader_view_exception(hass: HomeAssistant) -> None:
    """Test exception generating config."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
        )
    }
    mock_manager.async_consume_next_boot_option.side_effect = Exception("Boom")
    view = BootloaderView(mock_manager)

    mock_bootloader = MagicMock()
    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 500
