"""Pluggable bootloader modules."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohttp import web

LOGGER = logging.getLogger(__name__)


class BootloaderBase:
    """Base class for bootloaders."""

    name: str = "base"

    def generate_boot_config(self, host: dict[str, Any]) -> web.Response:
        """Generate the boot configuration response."""
        raise NotImplementedError


# This can be used to register bootloaders automatically
_BOOTLOADERS: dict[str, type[BootloaderBase]] = {}
# Cache failed imports to prevent I/O thread pool exhaustion from malicious requests
_FAILED_BOOTLOADERS: set[str] = set()


def register_bootloader(bootloader_cls: type[BootloaderBase]) -> type[BootloaderBase]:
    """Register a bootloader class."""
    _BOOTLOADERS[bootloader_cls.name] = bootloader_cls
    return bootloader_cls


def _load_bootloader_module(name: str) -> None:
    """Load a bootloader module synchronously."""
    importlib.import_module(f".{name}", __package__)


async def async_get_bootloader(hass: Any, name: str) -> BootloaderBase | None:
    """Get a bootloader instance by name."""
    if name in _FAILED_BOOTLOADERS:
        return None

    if name not in _BOOTLOADERS:
        try:
            # Dynamically importing modules performs blocking file I/O, so it must be
            # offloaded to an executor thread.
            await hass.async_add_executor_job(_load_bootloader_module, name)
        except ImportError:
            _FAILED_BOOTLOADERS.add(name)
            LOGGER.exception("Failed to load bootloader %s", name)
            return None

    bootloader_class = _BOOTLOADERS.get(name)
    if not bootloader_class:
        return None
    return bootloader_class()
