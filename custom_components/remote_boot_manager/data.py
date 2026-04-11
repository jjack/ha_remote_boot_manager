"""Custom types for remote_boot_manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .manager import RemoteBootManagerDataUpdateCoordinator


type RemoteBootManagerConfigEntry = ConfigEntry[RemoteBootManagerData]


@dataclass
class RemoteBootManagerData:
    """Data for the RemoteBootManager integration."""

    coordinator: RemoteBootManagerDataUpdateCoordinator
    integration: Integration
