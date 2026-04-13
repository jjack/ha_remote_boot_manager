"""Adds config flow for RemoteBootManager."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN, WEBHOOK_ID


class RemoteBootManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for RemoteBootManager."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._webhook_id: str = WEBHOOK_ID

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, (  # noqa: S101
            "Integration documentation URL is not set in manifest.json"
        )

        if user_input is not None:
            if user_input.get("generate_random_webhook_id"):
                self._webhook_id = webhook.async_generate_id()
                return await self.async_step_webhook_info()

            self._webhook_id = user_input.get("webhook_id", WEBHOOK_ID)
            return self.async_create_entry(
                title="Remote Boot Manager", data={"webhook_id": self._webhook_id}
            )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "webhook_id",
                    default=WEBHOOK_ID,
                ): str,
                vol.Optional(
                    "generate_random_webhook_id",
                    default=False,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors={},
            description_placeholders={
                "documentation_url": integration.documentation,
            },
        )

    async def async_step_webhook_info(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the generated webhook ID to the user."""
        if user_input is not None:
            return self.async_create_entry(
                title="Remote Boot Manager", data={"webhook_id": self._webhook_id}
            )

        webhook_url = webhook.async_generate_url(self.hass, self._webhook_id)

        return self.async_show_form(
            step_id="webhook_info",
            description_placeholders={
                "webhook_id": self._webhook_id,
                "webhook_url": webhook_url,
            },
        )
