"""Adds config flow for RemoteBootManager."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.loader import async_get_loaded_integration

from .const import BOOT_AGENT_URL, DEFAULT_NAME, DOMAIN


class RemoteBootManagerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for RemoteBootManager."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._webhook_id: str = ""

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        if integration.documentation is None:
            return self.async_abort(reason="missing_documentation")

        if user_input is not None:
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
                "agent_url": BOOT_AGENT_URL,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return RemoteBootManagerOptionsFlowHandler(config_entry)


class RemoteBootManagerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for remote_boot_manager."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.mac_to_edit: str | None = None

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the servers."""
        if user_input is not None:
            action = user_input["action"]
            if action == "add":
                return await self.async_step_add()
            elif action == "edit":
                return await self.async_step_edit_select()
            elif action == "remove":
                return await self.async_step_remove()

        manager = self.config_entry.runtime_data

        server_list = ""
        if manager and manager.servers:
            for mac, srv in manager.servers.items():
                server_list += f"- **{srv.name}** ({mac})\n"
        else:
            server_list += "- *None*\n"

        actions = {
            "add": "Add new server",
        }
        if manager and manager.servers:
            actions["edit"] = "Edit existing server"
            actions["remove"] = "Remove server"

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="add"): vol.In(actions)
            }),
            description_placeholders={"servers": server_list},
        )

    async def async_step_add(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new server."""
        errors = {}

        if user_input is not None:
            mac = format_mac(str(user_input["mac"]))
            manager = self.config_entry.runtime_data

            if not mac:
                errors["mac"] = "invalid_mac"
            elif mac in manager.servers:
                errors["mac"] = "mac_exists"
            else:
                payload = {
                    "name": user_input.get("name") or DEFAULT_NAME,
                    "host": user_input.get("host") or None,
                    "broadcast_address": user_input.get("broadcast_address") or None,
                    "broadcast_port": user_input.get("broadcast_port"),
                }
                manager.async_process_webhook_payload(mac, payload)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add",
            data_schema=vol.Schema({
                vol.Required("mac"): str,
                vol.Required("name"): str,
                vol.Optional("host"): str,
                vol.Optional("broadcast_address"): str,
                vol.Optional("broadcast_port"): cv.port,
            }),
            errors=errors,
        )

    async def async_step_edit_select(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select a server to edit."""
        manager = self.config_entry.runtime_data
        if user_input is not None:
            self.mac_to_edit = user_input["mac"]
            return await self.async_step_edit()

        server_options = {
            mac: f"{srv.name} ({mac})"
            for mac, srv in manager.servers.items()
        }

        return self.async_show_form(
            step_id="edit_select",
            data_schema=vol.Schema({
                vol.Required("mac"): vol.In(server_options)
            }),
        )

    async def async_step_edit(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit an existing server."""
        manager = self.config_entry.runtime_data
        server = manager.servers[self.mac_to_edit]

        if user_input is not None:
            payload = {
                "name": user_input["name"],
                "host": user_input.get("host") or None,
                "broadcast_address": user_input.get("broadcast_address") or None,
                "broadcast_port": user_input.get("broadcast_port"),
                "bootloader": server.bootloader,
                "boot_options": server.boot_options,
            }
            manager.async_process_webhook_payload(self.mac_to_edit, payload)
            return self.async_create_entry(title="", data={})

        schema = {}
        if server.name:
            schema[vol.Required("name", default=server.name)] = str
        else:
            schema[vol.Required("name")] = str
            
        schema[vol.Optional("host", default=server.host) if server.host else vol.Optional("host")] = str

        schema[vol.Optional("broadcast_address", default=server.broadcast_address) if server.broadcast_address else vol.Optional("broadcast_address")] = str
        schema[vol.Optional("broadcast_port", default=server.broadcast_port) if server.broadcast_port else vol.Optional("broadcast_port")] = cv.port

        warning = ""
        if server.bootloader or len(server.boot_options) > 1:
            warning = "⚠️ **Warning:** This server appears to be managed by a Remote Boot Agent. Any changes made here may be overwritten the next time the agent checks in."

        return self.async_show_form(
            step_id="edit", data_schema=vol.Schema(schema), description_placeholders={"warning": warning}
        )

    async def async_step_remove(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a server."""
        manager = self.config_entry.runtime_data
        if user_input is not None:
            mac = user_input["mac"]
            manager.async_remove_server(mac)
            
            device_reg = dr.async_get(self.hass)
            device = device_reg.async_get_device(identifiers={(DOMAIN, mac)})
            if device:
                device_reg.async_remove_device(device.id)
            
            return self.async_create_entry(title="", data={})

        server_options = {mac: f"{srv.name} ({mac})" for mac, srv in manager.servers.items()}
        return self.async_show_form(
            step_id="remove",
            data_schema=vol.Schema({vol.Required("mac"): vol.In(server_options)}),
        )

    async def async_step_reconfigure(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if user_input is not None:
            self._webhook_id = webhook.async_generate_id()
            return await self.async_step_reconfigure_webhook_info()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema({}),
        )

    async def async_step_reconfigure_webhook_info(
        self,
        user_input: dict | None = None,
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
                "agent_url": BOOT_AGENT_URL,
            },
        )
