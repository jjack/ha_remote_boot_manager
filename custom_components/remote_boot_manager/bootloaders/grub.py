"""GRUB bootloader module."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from . import BootloaderBase, register_bootloader


@register_bootloader
class GrubBootloader(BootloaderBase):
    """GRUB bootloader implementation."""

    name = "grub"

    def generate_boot_config(self, server: dict[str, Any]) -> web.Response:
        """Generate the GRUB boot configuration response."""
        next_boot_option = server.get("next_boot_option", "(none)")
        if next_boot_option != "(none)":
            content = f"set defaults='{next_boot_option}'\n"
        else:
            # returning nothing causes GRUB to fall back to its default behavior
            content = ""

        return web.Response(text=content, content_type="text/plain")
