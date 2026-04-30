"""Tests for Remote Boot Manager switch."""

from unittest.mock import MagicMock, patch

from custom_components.remote_boot_manager.manager import RemoteServer
from custom_components.remote_boot_manager.switch import (
    RemoteBootManagerSwitch,
    _async_ping_host,
    async_setup_entry,
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


async def test_async_setup_entry(hass):
    """Test the setup entry logic, including the dispatcher connection."""
    mock_entry = MagicMock()
    mock_manager = MagicMock()
    mock_manager.servers = {"00:11:22:33:44:55": MagicMock()}
    mock_entry.runtime_data = mock_manager
    async_add_entities = MagicMock()

    with patch(
        "custom_components.remote_boot_manager.switch.async_dispatcher_connect"
    ) as mock_connect:
        await async_setup_entry(hass, mock_entry, async_add_entities)

        assert async_add_entities.call_count == 1
        mock_connect.assert_called_once()
        mock_entry.async_on_unload.assert_called_once()

        # Verify the dispatcher callback adds the new entity
        callback = mock_connect.call_args[0][2]
        mock_manager.servers["AA:BB:CC:DD:EE:FF"] = MagicMock()
        callback("AA:BB:CC:DD:EE:FF")
        assert async_add_entities.call_count == 2


async def test_switch_async_update(hass):
    """Test switch async_update polling functionality."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
            bootloader="grub",
            host="192.168.1.100",
        )
    }

    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
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
            bootloader="grub",
            host="192.168.1.100",
        )
    }

    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
    switch.hass = hass

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
    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
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
    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
    switch.hass = hass

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

        # Close the coroutine that was passed into the mock to prevent RuntimeWarnings
        mock_create_task.call_args[0][0].close()


async def test_switch_async_turn_off(hass):
    """Test the turn off action."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55",
            name="Test Server",
        )
    }
    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
    switch.hass = hass

    # Simply verify it doesn't raise, as turning off WOL is not possible
    await switch.async_turn_off()


async def test_switch_async_ping_loop_success(hass):
    """Test the background ping loop resolving successfully."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            side_effect=[False, True],
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100")
        assert mock_ping.call_count == 2
        assert switch._attr_is_on is True
        switch.async_write_ha_state.assert_called_once()


async def test_switch_async_ping_loop_timeout(hass):
    """Test the background ping loop timing out after 3 minutes."""
    manager = MagicMock()
    manager.servers = {
        "00:11:22:33:44:55": RemoteServer(
            mac="00:11:22:33:44:55", name="Test", host="192.168.1.100"
        )
    }
    switch = RemoteBootManagerSwitch(manager, "00:11:22:33:44:55")
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    with (
        patch("asyncio.sleep"),
        patch(
            "custom_components.remote_boot_manager.switch._async_ping_host",
            return_value=False,
        ) as mock_ping,
    ):
        await switch._async_ping_loop("192.168.1.100")
        assert mock_ping.call_count == 36
        assert switch._attr_is_on is False
        switch.async_write_ha_state.assert_not_called()
