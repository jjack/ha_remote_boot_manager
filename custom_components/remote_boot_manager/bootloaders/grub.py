"""GRUB bootloader module."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from ..const import DEFAULT_BOOT_OPTION_NONE
from . import BootloaderBase, register_bootloader


@register_bootloader
class GrubBootloader(BootloaderBase):
    """GRUB bootloader implementation."""

    name = "grub"

    def generate_boot_config(self, host: dict[str, Any]) -> web.Response:
        """Generate the GRUB boot configuration response."""
        next_boot_option = host.get("next_boot_option", DEFAULT_BOOT_OPTION_NONE)
        if next_boot_option != DEFAULT_BOOT_OPTION_NONE:
            # Escape single quotes to prevent GRUB configuration injection
            safe_option = next_boot_option.replace("'", "\\'")
            content = f"set default='{safe_option}'\n"
        else:
            # returning nothing causes GRUB to fall back to its default behavior
            content = ""

        return web.Response(text=content, content_type="text/plain")
