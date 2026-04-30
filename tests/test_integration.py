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
    assert await async_setup_component(hass, "homeassistant", {})
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
        "name": "test-server",
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
        "name": "test-server",
        "bootloader": "grub",
        "boot_options": ["ubuntu", "windows"],
    }

    resp = await client.post(webhook_url, json=payload)
    assert resp.status == 200
    await hass.async_block_till_done()

    entity_id_select = "select.test_server_next_boot_option"
    entity_id_switch = "switch.test_server"

    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state == DEFAULT_BOOT_OPTION_NONE

    state = hass.states.get(entity_id_switch)
    assert state is not None


async def test_minimal_webhook_discovery_and_switch(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test discovery and switch functionality with a minimal payload (mac and name)."""
    client = setup_integration
    webhook_url = "/api/webhook/test_webhook_id"
    payload = {"mac": "de:ad:be:ef:00:01", "name": "minimal-server"}

    resp = await client.post(webhook_url, json=payload)
    assert resp.status == 200
    await hass.async_block_till_done()

    # Verify entities are created
    entity_id_switch = "switch.minimal_server"
    entity_id_select = "select.minimal_server_next_boot_option"

    assert hass.states.get(entity_id_switch) is not None
    select_state = hass.states.get(entity_id_select)
    assert select_state is not None
    assert select_state.attributes.get("options") == [DEFAULT_BOOT_OPTION_NONE]

    # Verify the switch works by calling turn_on
    with patch(
        "custom_components.remote_boot_manager.switch.wakeonlan.send_magic_packet"
    ) as mock_wake:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": entity_id_switch}, blocking=True
        )
        # With no broadcast args, it should be called with just the MAC
        mock_wake.assert_called_once_with("de:ad:be:ef:00:01")


async def test_webhook_with_host_enables_polling(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test that a payload with a host enables switch polling."""
    client = setup_integration
    webhook_url = "/api/webhook/test_webhook_id"
    payload = {"mac": "de:ad:be:ef:00:02", "name": "ping-server", "host": "127.0.0.1"}
    await client.post(webhook_url, json=payload)
    await hass.async_block_till_done()

    with patch(
        "custom_components.remote_boot_manager.switch._async_ping_host",
        return_value=True,
    ) as mock_ping:
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": "switch.ping_server"},
            blocking=True,
        )
        mock_ping.assert_called_once_with("127.0.0.1")


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


async def test_switch_turn_on_resets_boot_option(
    hass: HomeAssistant, discovered_client
) -> None:
    """Test that turning on the wake server switch sends magic packet and resets boot option."""
    entity_id_select = "select.test_server_next_boot_option"
    entity_id_switch = "switch.test_server"

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

    # Next, turn on the switch
    with patch(
        "custom_components.remote_boot_manager.switch.wakeonlan.send_magic_packet"
    ) as mock_wake:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": entity_id_switch},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_wake.assert_called_once_with("aa:bb:cc:dd:ee:ff")

    # Verify boot option does not reset to default
    state = hass.states.get(entity_id_select)
    assert state is not None
    assert state.state != DEFAULT_BOOT_OPTION_NONE


async def test_remove_integration_cleans_up(
    hass: HomeAssistant, discovered_client, mock_config_entry
) -> None:
    """Test that removing the integration cleans up devices and entities."""
    entity_id_select = "select.test_server_next_boot_option"
    entity_id_switch = "switch.test_server"

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id_select) is None
    assert hass.states.get(entity_id_switch) is None

    er = async_get_er(hass)
    dr = async_get_dr(hass)
    assert er.async_get(entity_id_select) is None
    assert er.async_get(entity_id_switch) is None

    device = dr.async_get_device(identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")})
    assert device is None


async def test_global_send_magic_packet_service(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test that the global send_magic_packet service works."""
    with patch(
        "custom_components.remote_boot_manager.__init__.wakeonlan.send_magic_packet"
    ) as mock_wake:
        await hass.services.async_call(
            DOMAIN,
            "send_magic_packet",
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "broadcast_address": "192.168.1.255",
                "broadcast_port": 9,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_wake.assert_called_once_with(
            "aa:bb:cc:dd:ee:ff", ip_address="192.168.1.255", port=9
        )
