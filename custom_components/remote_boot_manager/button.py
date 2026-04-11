"""Button platform for Remote Boot Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    async_add_entities([RemoteBootManagerButton()])


class RemoteBootManagerButton(ButtonEntity):
    """Remote Boot Manager button class."""

    _attr_has_entity_name = True
    _attr_name = "Remote Boot Button"

    async def async_press(self) -> None:
        """Handle the button press."""
        pass
