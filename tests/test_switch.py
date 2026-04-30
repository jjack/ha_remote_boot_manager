"""Tests for Remote Boot Manager switch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.remote_boot_manager.manager import RemoteServer
from custom_components.remote_boot_manager.switch import (
    PLATFORM_SCHEMA,
    RemoteBootManagerSwitch,
    _async_ping_host,
    async_setup_platform,
)


async def test_async_ping_host_alive():
    """Test the async ping command when host is alive."""
    mock_result = MagicMock()
    mock_result.is_alive = True
    with patch(
        "custom_components.remote_boot_manager.switch.async_ping",
        return_value=mock_result,
    ):
        assert await _async_ping_host("192.168.1.10") is True


async def test_async_ping_host_dead():
    """Test the async ping command when host is dead or throws an error."""
    with patch(
        "custom_components.remote_boot_manager.switch.async_ping",
        side_effect=Exception("Boom"),
    ):
        assert await _async_ping_host("192.168.1.10") is False


async def test_async_setup_platform_valid(hass):
    """Test setting up platform from YAML."""
    config = {
        "platform": "remote_boot_manager",
        "mac": "00:11:22:33:44:55",
        "name": "Test PC",
        "host": "192.168.1.100",
    }
    async_add_entities = MagicMock()
    await async_setup_platform(hass, config, async_add_entities)

    async_add_entities.assert_called_once()
    switch = async_add_entities.call_args[0][0][0]
    assert switch.server.mac == "00:11:22:33:44:55"
    assert switch.server.name == "Test PC"
    assert switch.server.host == "192.168.1.100"


def test_platform_schema_rejects_bootloader():
    """Test that the platform schema rejects legacy YAML with a bootloader."""
    config = {
        "platform": "remote_boot_manager",
        "mac": "00:11:22:33:44:55",
        "bootloader": "grub",
    }

    with pytest.raises(vol.Invalid) as exc:
        PLATFORM_SCHEMA(config)

    assert "backwards compatibility" in str(exc.value)


async def test_switch_async_update(hass):
    """Test switch async_update polling functionality."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            host="192.168.1.100",
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass

    with patch(
        "custom_components.remote_boot_manager.switch._async_ping_host",
        return_value=True,
    ):
        await switch.async_update()
        assert switch.is_on


async def test_switch_async_turn_on_starts_task(hass):
    """Test switch async_turn_on sends packet and starts the background ping loop."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            host="192.168.1.100",
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    with (
        patch(
            "custom_components.remote_boot_manager.switch.wakeonlan.send_magic_packet"
        ) as mock_send,
        patch.object(hass, "async_create_background_task") as mock_task,
    ):
        await switch.async_turn_on()
        await hass.async_block_till_done()

        mock_send.assert_called_once_with("00:11:22:33:44:55")
        mock_task.assert_called_once()
        assert switch.is_on is True
        switch.async_write_ha_state.assert_called_once()

        # Close the coroutine that was passed into the mock to prevent RuntimeWarnings
        mock_task.call_args[0][0].close()


async def test_switch_no_host_no_poll(hass):
    """Test that a server without a host doesn't poll or update state via ping."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            host=None,
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass

    assert switch.should_poll is False

    with patch(
        "custom_components.remote_boot_manager.switch._async_ping_host"
    ) as mock_ping:
        await switch.async_update()
        mock_ping.assert_not_called()


async def test_switch_async_turn_on_with_broadcast_and_cancels_task(hass):
    """Test sending a magic packet with custom broadcast data, cancelling old tasks."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            host="192.168.1.100",
            broadcast_address="192.168.1.255",
            broadcast_port=9,
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    # Mock an existing active ping task
    mock_task = MagicMock()
    mock_task.done.return_value = False
    switch._ping_task = mock_task

    with (
        patch(
            "custom_components.remote_boot_manager.switch.wakeonlan.send_magic_packet"
        ) as mock_send,
        patch.object(hass, "async_create_background_task") as mock_create_task,
    ):
        await switch.async_turn_on()
        await hass.async_block_till_done()

        mock_send.assert_called_once_with(
            "00:11:22:33:44:55", ip_address="192.168.1.255", port=9
        )
        mock_task.cancel.assert_called_once()
        mock_create_task.assert_called_once()
        assert switch.is_on is True
        switch.async_write_ha_state.assert_called_once()

        # Close the coroutine that was passed into the mock to prevent RuntimeWarnings
        mock_create_task.call_args[0][0].close()


async def test_switch_async_turn_off(hass):
    """Test the turn off action."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            host="192.168.1.100",
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()
    switch._attr_is_on = True

    mock_script = MagicMock()
    mock_script.async_run = AsyncMock()
    switch._turn_off_script = mock_script

    with patch.object(hass, "async_create_background_task") as mock_task:
        await switch.async_turn_off()
        assert switch.is_on is False
        switch.async_write_ha_state.assert_called_once()
        mock_script.async_run.assert_called_once()
        mock_task.assert_called_once()
        mock_task.call_args[0][0].close()


async def test_switch_async_ping_loop_success(hass):
    """Test the background ping loop resolving successfully."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()
    switch._attr_is_on = True

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            side_effect=[False, True],
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100", target_state=True)
        assert mock_ping.call_count == 2
        assert switch._attr_is_on is True
        switch.async_write_ha_state.assert_not_called()


async def test_switch_async_ping_loop_timeout(hass):
    """Test the background ping loop timing out after 3 minutes."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()
    switch._attr_is_on = True

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            return_value=False,
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100", target_state=True)
        assert mock_ping.call_count == 36
        assert switch._attr_is_on is False
        switch.async_write_ha_state.assert_called_once()


async def test_switch_async_ping_loop_off_success(hass):
    """Test the background ping off loop resolving successfully."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()
    switch._attr_is_on = False

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            side_effect=[True, False],
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100", target_state=False)
        assert mock_ping.call_count == 2
        assert switch._attr_is_on is False
        switch.async_write_ha_state.assert_not_called()


async def test_switch_async_ping_loop_off_timeout(hass):
    """Test the background ping off loop timing out after 3 minutes."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(hass, manager.servers["00:11:22:33:44:55"])
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()
    switch._attr_is_on = False

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            return_value=True,
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100", target_state=False)
        assert mock_ping.call_count == 36
        assert switch._attr_is_on is True
        switch.async_write_ha_state.assert_called_once()
