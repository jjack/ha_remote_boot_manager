"""Adds config flow for GrubOSSelectManager."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN, GRUB_OS_REPORTER_URL

if TYPE_CHECKING:
    from .data import GrubOSSelectManagerConfigEntry


class GrubOSSelectManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GrubOSSelectManager."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._webhook_id: str = ""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return GrubOSSelectManagerOptionsFlow(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        if integration.documentation is None:
            return self.async_abort(reason="missing_documentation")

        if user_input is not None:
            # Form has no fields; clicking submit confirms intent and triggers webhook
            # generation.
            self._webhook_id = webhook.async_generate_id()
            return await self.async_step_webhook_info()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            errors={},
            description_placeholders={
                "documentation_url": integration.documentation,
            },
        )

    async def async_step_webhook_info(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the generated webhook ID to the user."""
        if user_input is not None:
            return self.async_create_entry(
                title="Grub OS Selector", data={"webhook_id": self._webhook_id}
            )

        webhook_url = webhook.async_generate_url(self.hass, self._webhook_id)

        return self.async_show_form(
            step_id="webhook_info",
            description_placeholders={
                "webhook_id": self._webhook_id,
                "webhook_url": webhook_url,
                "reporter_url": GRUB_OS_REPORTER_URL,
            },
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if user_input is not None:
            # Form has no fields; clicking submit confirms intent and triggers webhook
            # sgeneration.
            self._webhook_id = webhook.async_generate_id()
            return await self.async_step_reconfigure_webhook_info()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
        )

    async def async_step_reconfigure_webhook_info(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the new webhook ID to the user."""
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data={"webhook_id": self._webhook_id},
            )

        webhook_url = webhook.async_generate_url(self.hass, self._webhook_id)

        return self.async_show_form(
            step_id="reconfigure_webhook_info",
            description_placeholders={
                "webhook_id": self._webhook_id,
                "webhook_url": webhook_url,
                "reporter_url": GRUB_OS_REPORTER_URL,
            },
        )


class GrubOSSelectManagerOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Grub OS Selector."""

    def __init__(self, config_entry: GrubOSSelectManagerConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self.selected_mac: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        manager = self._config_entry.runtime_data
        if not manager or not manager.hosts:
            return self.async_abort(reason="no_hosts")

        if user_input is not None:
            self.selected_mac = user_input["host"]
            return await self.async_step_host_config()

        hosts = {mac: f"{host.name} ({mac})" for mac, host in manager.hosts.items()}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): vol.In(hosts),
                }
            ),
        )

    async def async_step_host_config(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure specific host."""
        manager = self._config_entry.runtime_data

        if not self.selected_mac:
            return self.async_abort(reason="no_hosts")

        host = manager.hosts[self.selected_mac]

        if user_input is not None:
            if turn_off_script := user_input.get("turn_off_script"):
                # Save as a script sequence action
                host.off_action = [{"action": turn_off_script}]
            else:
                host.off_action = None

            host.address = user_input.get(CONF_ADDRESS)
            host.broadcast_address = user_input.get(CONF_BROADCAST_ADDRESS)
            host.broadcast_port = user_input.get(CONF_BROADCAST_PORT)

            # Persist the changes to storage
            manager.save()

            # Saving the entry data with a timestamp forces Home Assistant to trigger
            # the reload listener
            return self.async_create_entry(title="", data={"updated_at": time.time()})

        default_script = vol.UNDEFINED
        if (
            host.off_action
            and isinstance(host.off_action, list)
            and len(host.off_action) > 0
            and (action := host.off_action[0].get("action"))
        ):
            default_script = action

        data_schema = {}

        if default_script != vol.UNDEFINED:
            data_schema[
                vol.Optional(
                    "turn_off_script", description={"suggested_value": default_script}
                )
            ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="script"))
        else:
            data_schema[vol.Optional("turn_off_script")] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            )

        # Address values can be edited here for debugging but will be overwritten the
        # next time the reporter checks in.
        data_schema[
            vol.Optional(CONF_ADDRESS, description={"suggested_value": host.address})
            if host.address is not None
            else vol.Optional(CONF_ADDRESS)
        ] = str
        data_schema[
            vol.Optional(
                CONF_BROADCAST_ADDRESS,
                description={"suggested_value": host.broadcast_address},
            )
            if host.broadcast_address is not None
            else vol.Optional(CONF_BROADCAST_ADDRESS)
        ] = str
        data_schema[
            vol.Optional(
                CONF_BROADCAST_PORT,
                description={"suggested_value": host.broadcast_port},
            )
            if host.broadcast_port is not None
            else vol.Optional(CONF_BROADCAST_PORT)
        ] = int

        return self.async_show_form(
            step_id="host_config",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "host_name": host.name,
            },
        )
