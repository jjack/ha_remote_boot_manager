"""Tests for webhook functionality."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import web

from custom_components.remote_boot_manager.webhook import async_validate_webhook_payload


async def test_validate_webhook_empty_body():
    """Test validation with empty body."""
    request = MagicMock(spec=web.Request)
    request.text = AsyncMock(return_value="")

    payload, response = await async_validate_webhook_payload(request)
    assert payload is None
    assert response is not None
    assert response.status == 400
    assert response.text == "empty body"


async def test_validate_webhook_payload_too_large():
    """Test validation with oversized payload."""
    request = MagicMock(spec=web.Request)
    request.text = AsyncMock(return_value="a" * 102401)

    payload, response = await async_validate_webhook_payload(request)
    assert payload is None
    assert response is not None
    assert response.status == 413


async def test_validate_webhook_invalid_json():
    """Test validation with invalid JSON."""
    request = MagicMock(spec=web.Request)
    request.text = AsyncMock(return_value="invalid json")
    request.json = AsyncMock(side_effect=ValueError("Boom"))

    payload, response = await async_validate_webhook_payload(request)
    assert payload is None
    assert response is not None
    assert response.status == 400
    assert response.text == "Invalid JSON payload"


async def test_validate_webhook_invalid_schema():
    """Test validation with invalid schema."""
    request = MagicMock(spec=web.Request)
    request.text = AsyncMock(return_value='{"name": "test"}')  # missing mac
    request.json = AsyncMock(return_value={"name": "test"})

    payload, response = await async_validate_webhook_payload(request)
    assert payload is None
    assert response is not None
    assert response.status == 400
    assert response.text is not None
    assert "Invalid payload format" in response.text


async def test_validate_webhook_valid_payload():
    """Test validation with valid payload."""
    request = MagicMock(spec=web.Request)
    valid_data = {
        "mac": "00:11:22:33:44:55",
        "name": "test",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "windows"],
        "host": "192.168.1.100",
        "broadcast_address": "192.168.1.255",
        "broadcast_port": 9,
    }
    request.text = AsyncMock(
        return_value='{"mac": "00:11:22:33:44:55", "name": "test", "bootloader": "grub", "boot_options": ["ubuntu", "windows"], "host": "192.168.1.100", "broadcast_address": "192.168.1.255", "broadcast_port": 9}'
    )
    request.json = AsyncMock(return_value=valid_data)

    payload, response = await async_validate_webhook_payload(request)
    assert response is None
    assert payload is not None
    assert payload["mac"] == "00:11:22:33:44:55"
    assert payload["name"] == "test"
    assert payload["bootloader"] == "grub"
    assert payload["boot_options"] == ["ubuntu", "windows"]
    assert payload["host"] == "192.168.1.100"
    assert payload["broadcast_address"] == "192.168.1.255"
    assert payload["broadcast_port"] == 9
    assert payload["entity_type"] == "button"


async def test_validate_webhook_entity_type():
    """Test validation with explicit and invalid entity types."""
    request = MagicMock(spec=web.Request)

    # Explicit valid entity type
    request.text = AsyncMock(return_value="{}")
    request.json = AsyncMock(
        return_value={
            "mac": "00:11:22:33:44:55",
            "name": "test",
            "entity_type": "switch",
        }
    )
    payload, response = await async_validate_webhook_payload(request)
    assert response is None
    assert payload is not None
    assert payload["entity_type"] == "switch"

    # Invalid entity type
    request.json = AsyncMock(
        return_value={
            "mac": "00:11:22:33:44:55",
            "name": "test",
            "entity_type": "sensor",
        }
    )
    payload, response = await async_validate_webhook_payload(request)
    assert payload is None
    assert response is not None
    assert response.status == 400
