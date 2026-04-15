"""Test the config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.const import DOMAIN


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.remote_boot_manager.config_flow.webhook.async_generate_url",
        return_value="http://example.com/webhook",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "webhook_info"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {},
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Remote Boot Manager"
    assert "webhook_id" in result3["data"]


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only a single instance is allowed."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"

async def test_webhook_generation_failed(hass: HomeAssistant) -> None:
    """Test when webhook ID is not set."""
    flow = config_entries.HANDLERS[DOMAIN]()
    flow.hass = hass
    # _webhook_id is None by default
    result = await flow.async_step_webhook_info()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "webhook_id_generation_failed"
