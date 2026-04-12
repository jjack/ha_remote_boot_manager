"""GRUB bootloader module."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from . import BootloaderBase, register_bootloader


@register_bootloader
class GrubBootloader(BootloaderBase):
    """GRUB bootloader implementation."""

    name = "grub"

    def get_boot_config(self, server: dict[str, Any]) -> web.Response:
        """Generate the GRUB boot configuration response."""

        selected_os = server.get("selected_os", "(none)")
        if selected_os != "(none)":
            content = f"set defaults='{selected_os}'\n"
        else:
            # returning nothing causes GRUB to fall back to its default behavior
            content = ""

        return web.Response(text=content, content_type="text/plain")
