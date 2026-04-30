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
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    with patch(
        "custom_components.remote_boot_manager.config_flow.webhook.async_generate_url",
        return_value="http://example.com/webhook",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "webhook_info"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Remote Boot Manager"
    assert "webhook_id" in result3.get("data", {})


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test that only a single instance is allowed."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "test_id"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure flow to regenerate webhook ID."""
    entry = MockConfigEntry(domain=DOMAIN, data={"webhook_id": "old_id"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    with (
        patch(
            "custom_components.remote_boot_manager.config_flow.webhook.async_generate_id",
            return_value="new_id",
        ),
        patch(
            "custom_components.remote_boot_manager.config_flow.webhook.async_generate_url",
            return_value="http://example.com/new_webhook",
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reconfigure_webhook_info"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={},
    )

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reconfigure_successful"
    assert entry.data["webhook_id"] == "new_id"
