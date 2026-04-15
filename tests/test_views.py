"""Test views for remote_boot_manager."""
from unittest.mock import MagicMock, patch

from aiohttp import web
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.views import BootloaderView


async def test_bootloader_view_invalid_mac(hass: HomeAssistant) -> None:
    """Test Invalid MAC."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    with patch("custom_components.remote_boot_manager.views.format_mac", return_value=None):
        resp = await view.get(mock_request, "invalid")
        assert resp.status == 400

async def test_bootloader_view_integration_not_ready(hass: HomeAssistant) -> None:
    """Test integration not ready."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    # No config entries in hass returns 503
    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == 503

async def test_bootloader_view_server_not_found(hass: HomeAssistant) -> None:
    """Test server not found."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {}
    mock_entry = MockConfigEntry(domain="remote_boot_manager")
    mock_entry.add_to_hass(hass)
    mock_entry.runtime_data = mock_manager

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == 404

async def test_bootloader_view_unsupported_bootloader(hass: HomeAssistant) -> None:
    """Test unsupported bootloader."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {"aa:bb:cc:dd:ee:ff": {"bootloader": "unsupported"}}
    mock_entry = MockConfigEntry(domain="remote_boot_manager")
    mock_entry.add_to_hass(hass)
    mock_entry.runtime_data = mock_manager

    with patch("custom_components.remote_boot_manager.views.async_get_bootloader", return_value=None):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 400

async def test_bootloader_view_exception(hass: HomeAssistant) -> None:
    """Test exception generating config."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {"aa:bb:cc:dd:ee:ff": {"bootloader": "grub"}}
    mock_manager.async_consume_selected_os.side_effect = Exception("Boom")
    mock_entry = MockConfigEntry(domain="remote_boot_manager")
    mock_entry.add_to_hass(hass)
    mock_entry.runtime_data = mock_manager

    mock_bootloader = MagicMock()
    with patch("custom_components.remote_boot_manager.views.async_get_bootloader", return_value=mock_bootloader):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == 500

