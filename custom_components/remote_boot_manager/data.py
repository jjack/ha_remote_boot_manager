"""Custom types for remote_boot_manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import RemoteBootManagerApiClient
    from .coordinator import RemoteBootManagerDataUpdateCoordinator


type RemoteBootManagerConfigEntry = ConfigEntry[RemoteBootManagerData]


@dataclass
class RemoteBootManagerData:
    """Data for the RemoteBootManager integration."""

    client: RemoteBootManagerApiClient
    coordinator: RemoteBootManagerDataUpdateCoordinator
    integration: Integration
