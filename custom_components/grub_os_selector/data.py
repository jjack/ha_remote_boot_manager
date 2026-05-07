"""Custom types for grub_os_selector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .manager import GrubOSSelectManager

type GrubOSSelectManagerConfigEntry = ConfigEntry["GrubOSSelectManager"]
