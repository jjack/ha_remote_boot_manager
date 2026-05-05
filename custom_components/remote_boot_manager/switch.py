"""Switch platform for Remote Boot Manager."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING, Any

import wakeonlan
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.script import Script
from icmplib import async_ping

from .const import (
    DOMAIN,
    SIGNAL_NEW_SERVER,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import RemoteBootManagerConfigEntry
    from .manager import RemoteServer


async def _async_ping_host(host: str) -> bool:
    """Ping the given host asynchronously."""
    try:
        # privileged=False allows pinging without root privileges on most modern systems
        result = await async_ping(host, count=1, timeout=1, privileged=False)
    except Exception:  # noqa: BLE001
        return False
    else:
        return result.is_alive


class RemoteBootManagerSwitch(SwitchEntity):
    """Remote Boot Manager switch class."""

    def __init__(
        self,
        hass: HomeAssistant,
        server: RemoteServer,
    ) -> None:
        """Initialize the switch class."""
        self.server = server

        self._attr_unique_id = f"{self.server.mac}_wake_switch"
        self._attr_name = "Wake"
        self._attr_has_entity_name = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_is_on = False

        self._ping_task: asyncio.Task | None = None
        self._turn_off_script = (
            Script(hass, self.server.off_action, self.server.name, DOMAIN)
            if self.server.off_action
            else None
        )

        broadcast_info = []
        if b_addr := self.server.broadcast_address:
            broadcast_info.append(f"IP: {b_addr}")
        if b_port := self.server.broadcast_port:
            broadcast_info.append(f"Port: {b_port}")

        model_name = f"WOL ({', '.join(broadcast_info)})" if broadcast_info else "WOL"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.server.mac)},
            name=self.server.name,
            manufacturer="Remote Boot Manager",
            model=model_name,
            connections={(CONNECTION_NETWORK_MAC, self.server.mac)},
        )

    @property
    def _ping_target(self) -> str | None:
        """Return the target IP or hostname to ping."""
        return self.server.address

    @property
    def assumed_state(self) -> bool:
        """Flag this entity as unverified if we cannot ping it."""
        return not bool(self._ping_target)

    @property
    def should_poll(self) -> bool:
        """Enable polling only if we have a host to ping."""
        return bool(self._ping_target)

    async def async_update(self) -> None:
        """Update entity state via standard polling."""
        target = self._ping_target
        if not target:
            return

        # don't change the state until the ping task is done
        if self._ping_task and not self._ping_task.done():
            return

        self._attr_is_on = await _async_ping_host(target)

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the entity on."""
        self._attr_is_on = True
        self.async_write_ha_state()

        wol_kwargs = {}
        if self.server.broadcast_address is not None:
            wol_kwargs["ip_address"] = self.server.broadcast_address
        if self.server.broadcast_port is not None:
            wol_kwargs["port"] = self.server.broadcast_port

        await self.hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, self.server.mac, **wol_kwargs)
        )

        target = self._ping_target
        if target:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            self._ping_task = self.hass.async_create_background_task(
                self._async_ping_loop(target, target_state=True),
                "wol_ping_on",
            )

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the entity off if a turn_off script was defined."""
        self._attr_is_on = False
        self.async_write_ha_state()

        if self._turn_off_script:
            await self._turn_off_script.async_run(context=self._context)

        target = self._ping_target
        if target:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            self._ping_task = self.hass.async_create_background_task(
                self._async_ping_loop(target, target_state=False),
                "wol_ping_off",
            )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up background tasks when the entity is removed."""
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
        await super().async_will_remove_from_hass()

    async def _async_ping_loop(self, host: str, *, target_state: bool) -> None:
        """Ping host rapidly for 3 minutes after turn-on/off."""
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return

        for _ in range(36):  # 36 iterations * 5 seconds = 180 seconds (3 mins)
            is_awake = await _async_ping_host(host)
            if is_awake == target_state:
                return
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                return

        self._attr_is_on = not target_state
        if self.hass is not None:
            self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform from a config entry."""
    manager = entry.runtime_data

    @callback
    def async_add_server_switch(mac_address: str) -> None:
        """Add a switch entity for a newly discovered server."""
        server = manager.servers[mac_address]
        async_add_entities([RemoteBootManagerSwitch(hass, server)])

    # Add entities for servers that already exist in the manager
    for mac in manager.servers:
        async_add_server_switch(mac)

    # Listen for the signal to add new servers discovered via webhook
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_SERVER, async_add_server_switch)
    )
