"""Test integration for remote_boot_manager."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import async_get as async_get_dr
from homeassistant.helpers.entity_registry import async_get as async_get_er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.remote_boot_manager.const import DEFAULT_BOOT_OPTION_NONE, DOMAIN


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Remote Boot Manager",
        data={"webhook_id": "test_webhook_id"},
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant, hass_client, mock_config_entry):
    """Set up the integration and return the web client."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "webhook", {})
    await hass.async_block_till_done()

    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return client


@pytest.fixture
async def discovered_client(hass: HomeAssistant, setup_integration):
    """Return a client after discovering a test server via webhook."""
    client = setup_integration
    webhook_url = "/api/webhook/test_webhook_id"
    payload = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "test-server",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "windows"],
    }
    resp = await client.post(webhook_url, json=payload)
    assert resp.status == 200
    await hass.async_block_till_done()
    return client


async def test_webhook_discovery(hass: HomeAssistant, setup_integration) -> None:
    """Test that posting to the webhook creates the appropriate entities."""
    client = setup_integration
    webhook_url = "/api/webhook/test_webhook_id"
    payload = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "hostname": "test-server",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "windows"],
    }

    resp = await client.post(webhook_url, json=payload)
    assert resp.status == 200
    await hass.async_block_till_done()

    entity_id_select = "select.test_server_next_boot_option"
    entity_id_button = "button.test_server_wake_server"

    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state == DEFAULT_BOOT_OPTION_NONE

    state = hass.states.get(entity_id_button)
    assert state is not None


async def test_select_and_bootloader_view(
    hass: HomeAssistant, discovered_client
) -> None:
    """Test selecting a boot option and retrieving the bootloader view."""
    client = discovered_client
    entity_id_select = "select.test_server_next_boot_option"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id_select, "option": "ubuntu"},
        blocking=True,
    )

    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state == "ubuntu"

    resp = await client.get("/api/remote_boot_manager/aa:bb:cc:dd:ee:ff")
    assert resp.status == 200
    text = await resp.text()
    assert 'grub-reboot "ubuntu"' in text or "ubuntu" in text


async def test_button_press_resets_boot_option(
    hass: HomeAssistant, discovered_client
) -> None:
    """Test that pressing the wake server button sends magic packet and resets boot option."""
    entity_id_select = "select.test_server_next_boot_option"
    entity_id_button = "button.test_server_wake_server"

    # First, select a boot option
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id_select, "option": "windows"},
        blocking=True,
    )
    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state == "windows"

    # Next, press the button
    with patch("wakeonlan.send_magic_packet") as mock_wake:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": entity_id_button},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_wake.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    # Verify boot option resets to default
    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state == DEFAULT_BOOT_OPTION_NONE


async def test_remove_integration_cleans_up(
    hass: HomeAssistant, discovered_client, mock_config_entry
) -> None:
    """Test that removing the integration cleans up devices and entities."""
    entity_id_select = "select.test_server_next_boot_option"
    entity_id_button = "button.test_server_wake_server"

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id_select) is None
    assert hass.states.get(entity_id_button) is None

    er = async_get_er(hass)
    dr = async_get_dr(hass)
    assert er.async_get(entity_id_select) is None
    assert er.async_get(entity_id_button) is None

    device = dr.async_get_device(identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")})
    assert device is None
