"""Binary sensor platform for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import RemoteBootManagerEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import RemoteBootManagerDataUpdateCoordinator
    from .data import RemoteBootManagerConfigEntry

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="remote_boot_manager",
        name="Remote Boot Manager Binary Sensor",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: RemoteBootManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        RemoteBootManagerBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class RemoteBootManagerBinarySensor(RemoteBootManagerEntity, BinarySensorEntity):
    """remote_boot_manager binary_sensor class."""

    def __init__(
        self,
        coordinator: RemoteBootManagerDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self.coordinator.data.get("title", "") == "foo"
