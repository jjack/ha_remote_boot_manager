"""Tests for the GRUB bootloader."""

from custom_components.remote_boot_manager.bootloaders.grub import GrubBootloader
from custom_components.remote_boot_manager.const import DEFAULT_BOOT_OPTION_NONE


def test_generate_boot_config_normal_option() -> None:
    """Test generating config with a normal standard boot option."""
    bootloader = GrubBootloader()
    host = {"next_boot_option": "Ubuntu"}
    response = bootloader.generate_boot_config(host)

    assert response.text == "set default='Ubuntu'\n"
    assert response.content_type == "text/plain"


def test_generate_boot_config_default_none() -> None:
    """Test generating config with the default '(none)' option."""
    bootloader = GrubBootloader()
    host = {"next_boot_option": DEFAULT_BOOT_OPTION_NONE}
    response = bootloader.generate_boot_config(host)

    assert response.text == ""


def test_generate_boot_config_missing_option() -> None:
    """Test generating config when next_boot_option is entirely missing."""
    bootloader = GrubBootloader()
    host = {}
    response = bootloader.generate_boot_config(host)

    assert response.text == ""


def test_generate_boot_config_injection_prevention() -> None:
    """Test that single quotes are correctly escaped to prevent GRUB injection."""
    bootloader = GrubBootloader()
    # A malicious or poorly formed string that attempts to break out of the single quotes
    host = {"next_boot_option": "Ubuntu'; rm -rf /; #"}
    response = bootloader.generate_boot_config(host)

    # The single quote should be escaped as \' preventing execution of subsequent commands
    assert response.text == "set default='Ubuntu\\'; rm -rf /; #'\n"
