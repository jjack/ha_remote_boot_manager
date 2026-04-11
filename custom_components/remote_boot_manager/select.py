"""Select platform for Remote Boot Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import DEFAULT_OS_NONE

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    async_add_entities([RemoteBootManagerSelect()])


class RemoteBootManagerSelect(SelectEntity):
    """Remote Boot Manager select class."""

    _attr_has_entity_name = True
    _attr_name = "Remote Boot Option"
    _attr_options = [DEFAULT_OS_NONE, "Debian", "Windows"]
    _attr_current_option = "Option 1"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self.async_write_ha_state()
