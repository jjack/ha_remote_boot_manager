"""Test views for remote_boot_manager."""

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from aiohttp import web
from homeassistant.core import HomeAssistant

from custom_components.remote_boot_manager.manager import RemoteServer
from custom_components.remote_boot_manager.views import BootloaderView


async def test_bootloader_view_invalid_mac(hass: HomeAssistant) -> None:
    """Test Invalid MAC."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    with patch(
        "custom_components.remote_boot_manager.views.format_mac", return_value=None
    ):
        resp = await view.get(mock_request, "invalid")
        assert resp.status == HTTPStatus.BAD_REQUEST


async def test_bootloader_view_server_not_found(hass: HomeAssistant) -> None:
    """Test server not found."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {}

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_manager
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    view = BootloaderView()

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_bootloader_view_no_bootloader(hass: HomeAssistant) -> None:
    """Test server with no bootloader configured."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader=None,
        )
    }

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_manager
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    view = BootloaderView()

    resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
    assert resp.status == HTTPStatus.BAD_REQUEST


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

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_manager
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    view = BootloaderView()

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=None,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == HTTPStatus.BAD_REQUEST


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
    mock_request.query = {}

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_manager
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    view = BootloaderView()

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.side_effect = Exception("Boom")
    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_bootloader_view_success_read_only(hass: HomeAssistant) -> None:
    """Test successful request without a valid token (read-only)."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    mock_request.query = {}

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
            next_boot_option="windows",
        )
    }

    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_manager
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    view = BootloaderView()

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.return_value = web.Response(text="ok")

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == HTTPStatus.OK
        mock_manager.async_consume_next_boot_option.assert_not_called()

        # Verify the unconsumed next_boot_option is passed to the generator
        called_server = mock_bootloader.generate_boot_config.call_args[0][0]
        assert called_server["next_boot_option"] == "windows"


async def test_bootloader_view_success_consume(hass: HomeAssistant) -> None:
    """Test successful request with a valid token (consumes state)."""
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}
    mock_request.query = {"token": "valid_webhook_id"}

    mock_entry = MagicMock()
    mock_entry.data = {"webhook_id": "valid_webhook_id"}
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    mock_manager = MagicMock()
    mock_manager.servers = {
        "aa:bb:cc:dd:ee:ff": RemoteServer(
            mac="aa:bb:cc:dd:ee:ff",
            name="test",
            bootloader="grub",
            next_boot_option="windows",
        )
    }
    mock_manager.async_consume_next_boot_option.return_value = "windows"

    mock_entry.runtime_data = mock_manager
    view = BootloaderView()

    mock_bootloader = MagicMock()
    mock_bootloader.generate_boot_config.return_value = web.Response(text="ok")

    with patch(
        "custom_components.remote_boot_manager.views.async_get_bootloader",
        return_value=mock_bootloader,
    ):
        resp = await view.get(mock_request, "aa:bb:cc:dd:ee:ff")
        assert resp.status == HTTPStatus.OK
        mock_manager.async_consume_next_boot_option.assert_called_once_with(
            "aa:bb:cc:dd:ee:ff"
        )

        called_server = mock_bootloader.generate_boot_config.call_args[0][0]
        assert called_server["next_boot_option"] == "windows"


async def test_bootloader_view_integration_not_configured(hass: HomeAssistant) -> None:
    """Test that BootloaderView handles missing config entries gracefully."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    with patch.object(hass.config_entries, "async_entries", return_value=[]):
        response = await view.get(mock_request, "00:11:22:33:44:55")

        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
        body = json.loads(response.text)
        assert body["error"] == "Integration not configured"


async def test_bootloader_view_integration_not_ready(hass: HomeAssistant) -> None:
    """Test that BootloaderView handles an integration that isn't ready."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_entry = MagicMock()
    mock_entry.runtime_data = None

    with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
        response = await view.get(mock_request, "00:11:22:33:44:55")

        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
        body = json.loads(response.text)
        assert body["error"] == "Integration not ready"


async def test_bootloader_view_missing_documentation(hass: HomeAssistant) -> None:
    """Test that BootloaderView handles an integration missing documentation."""
    view = BootloaderView()
    mock_request = MagicMock(spec=web.Request)
    mock_request.app = {"hass": hass}

    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.servers = {}
    mock_entry.data = {"webhook_id": "valid_webhook_id"}

    with patch.object(hass.config_entries, "async_entries", return_value=[mock_entry]):
        response = await view.get(mock_request, "00:11:22:33:44:55")

        assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
        body = json.loads(response.text)
        assert body["error"] == "Integration missing documentation"
