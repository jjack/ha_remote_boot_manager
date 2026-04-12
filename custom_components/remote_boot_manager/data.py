"""Custom types for remote_boot_manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .manager import RemoteBootManager

type RemoteBootManagerConfigEntry = ConfigEntry["RemoteBootManager"]
