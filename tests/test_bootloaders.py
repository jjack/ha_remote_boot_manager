"""Tests for bootloader modules."""

from unittest.mock import patch

import pytest
from aiohttp import web

from custom_components.remote_boot_manager.bootloaders import (
    BootloaderBase,
    async_get_bootloader,
)
from custom_components.remote_boot_manager.bootloaders.grub import GrubBootloader


def test_base_bootloader_not_implemented() -> None:
    """Test that the base bootloader raises NotImplementedError."""
    base = BootloaderBase()
    with pytest.raises(NotImplementedError):
        base.generate_boot_config({})


@pytest.mark.parametrize("server_dict", [{}, {"next_boot_option": "(none)"}])
def test_grub_bootloader_default_option(server_dict) -> None:
    """Test GRUB bootloader generation with default or missing next_boot_option."""
    bootloader = GrubBootloader()
    response = bootloader.generate_boot_config(server_dict)

    assert isinstance(response, web.Response)
    assert response.text == ""
    assert response.content_type == "text/plain"


def test_grub_bootloader_custom_option() -> None:
    """Test GRUB bootloader generation with a custom boot option."""
    bootloader = GrubBootloader()
    response = bootloader.generate_boot_config({"next_boot_option": "windows"})

    assert isinstance(response, web.Response)
    assert response.text == "set default='windows'\n"
    assert response.content_type == "text/plain"


async def test_async_get_bootloader_valid(hass) -> None:
    """Test retrieving a valid bootloader."""
    bootloader = await async_get_bootloader(hass, "grub")
    assert isinstance(bootloader, GrubBootloader)


async def test_async_get_bootloader_invalid(hass) -> None:
    """Test retrieving an invalid bootloader (triggers ImportError)."""
    bootloader = await async_get_bootloader(hass, "invalid_bootloader_name")
    assert bootloader is None


async def test_async_get_bootloader_not_registered(hass) -> None:
    """Test retrieving a bootloader that loads but doesn't register itself."""
    with patch(
        "custom_components.remote_boot_manager.bootloaders._load_bootloader_module"
    ):
        bootloader = await async_get_bootloader(hass, "unregistered")
        assert bootloader is None
