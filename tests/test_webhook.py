"""Tests for webhook functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web

from custom_components.remote_boot_manager.webhook import (
    async_validate_webhook_payload,
    handle_boot_options_ingest_webhook,
)


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
    valid_data = {"mac": "00:11:22:33:44:55", "name": "test"}
    request.text = AsyncMock(
        return_value='{"mac": "00:11:22:33:44:55", "name": "test"}'
    )
    request.json = AsyncMock(return_value=valid_data)

    payload, response = await async_validate_webhook_payload(request)
    assert response is None
    assert payload is not None
    assert payload["mac"] == "00:11:22:33:44:55"
    assert payload["name"] == "test"


async def test_handle_webhook_none_payload(hass):
    """Test handling webhook with None payload (edge case)."""
    request = MagicMock(spec=web.Request)

    with patch(
        "custom_components.remote_boot_manager.webhook.async_validate_webhook_payload",
        return_value=(None, None),
    ):
        response = await handle_boot_options_ingest_webhook(hass, "test_id", request)
        assert response.status == 500
        assert response.text == "Unexpected empty payload"


async def test_handle_webhook_exception(hass):
    """Test handling webhook when an exception occurs."""
    request = MagicMock(spec=web.Request)

    with patch(
        "custom_components.remote_boot_manager.webhook.async_validate_webhook_payload",
        side_effect=Exception("Boom"),
    ):
        response = await handle_boot_options_ingest_webhook(hass, "test_id", request)
        assert response.status == 500
        assert response.text == "Internal Server Error"


async def test_handle_webhook_validation_error(hass):
    """Test handling webhook when payload validation returns an error response."""
    request = MagicMock(spec=web.Request)
    error_response = web.Response(status=400, text="Bad Request")

    with patch(
        "custom_components.remote_boot_manager.webhook.async_validate_webhook_payload",
        return_value=(None, error_response),
    ):
        response = await handle_boot_options_ingest_webhook(hass, "test_id", request)
        assert response is error_response
        assert response.status == 400
        assert response.text == "Bad Request"
