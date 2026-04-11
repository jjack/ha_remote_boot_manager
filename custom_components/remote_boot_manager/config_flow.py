"""Adds config flow for RemoteBootManager."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN


class RemoteBootManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for RemoteBootManager."""

    VERSION = 1

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
            # We don't really have any data to save, so we just pass an empty dict.
            return self.async_create_entry(title="Remote Boot Manager", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors={},
        )
