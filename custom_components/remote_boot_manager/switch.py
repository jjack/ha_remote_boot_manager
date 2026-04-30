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
from icmplib import async_ping

from .const import DOMAIN, SIGNAL_NEW_SERVER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import RemoteBootManagerConfigEntry
    from .manager import RemoteBootManager


async def _async_ping_host(host: str) -> bool:
    """Ping the given host asynchronously."""
    try:
        # privileged=False allows pinging without root privileges on most modern systems
        result = await async_ping(host, count=1, timeout=1, privileged=False)
    except Exception:  # noqa: BLE001
        return False
    else:
        return result.is_alive


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemoteBootManagerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    manager = entry.runtime_data

    @callback
    def async_add_server_switch(mac_address: str) -> None:
        """Add a switch entity for a newly discovered server."""
        async_add_entities([RemoteBootManagerSwitch(manager, mac_address)])

    # Add entities for servers that already exist in the manager
    for mac in manager.servers:
        async_add_server_switch(mac)

    # Listen for the signal to add new servers discovered via webhook
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_SERVER, async_add_server_switch)
    )


class RemoteBootManagerSwitch(SwitchEntity):
    """Remote Boot Manager switch class."""

    def __init__(
        self,
        manager: RemoteBootManager,
        mac_address: str,
    ) -> None:
        """Initialize the switch class."""
        self.manager = manager
        self.mac_address = mac_address
        self.server = manager.servers[mac_address]

        self._attr_unique_id = f"{mac_address}_wake_switch"
        self._attr_name = None
        self._attr_has_entity_name = True
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_is_on = False

        self._ping_task: asyncio.Task | None = None

        broadcast_info = []
        if b_addr := self.server.broadcast_address:
            broadcast_info.append(f"IP: {b_addr}")
        if b_port := self.server.broadcast_port:
            broadcast_info.append(f"Port: {b_port}")

        model_name = (
            f"Wake-on-LAN ({', '.join(broadcast_info)})"
            if broadcast_info
            else "Wake-on-LAN"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac_address)},
            name=self.server.name,
            manufacturer="Remote Boot Manager",
            model=model_name,
            connections={(CONNECTION_NETWORK_MAC, mac_address)},
        )

    @property
    def should_poll(self) -> bool:
        """Enable polling only if we have a host to ping."""
        return bool(self.server.host)

    async def async_update(self) -> None:
        """Update entity state via standard polling."""
        if not self.server.host:
            return
        self._attr_is_on = await _async_ping_host(self.server.host)

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the entity on."""
        wol_kwargs = {}
        if broadcast_address := self.server.broadcast_address:
            wol_kwargs["ip_address"] = broadcast_address
        if broadcast_port := self.server.broadcast_port:
            wol_kwargs["port"] = broadcast_port

        await self.hass.async_add_executor_job(
            partial(wakeonlan.send_magic_packet, self.mac_address, **wol_kwargs)
        )

        if self.server.host:
            if self._ping_task and not self._ping_task.done():
                self._ping_task.cancel()
            self._ping_task = self.hass.async_create_background_task(
                self._async_ping_loop(self.server.host), "wol_ping"
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off (Wake-on-LAN doesn't natively support off)."""

    async def _async_ping_loop(self, host: str) -> None:
        """Ping host rapidly for 3 minutes after turn-on."""
        await asyncio.sleep(10)
        for _ in range(36):  # 36 iterations * 5 seconds = 180 seconds (3 mins)
            is_awake = await _async_ping_host(host)
            if is_awake:
                self._attr_is_on = True
                self.async_write_ha_state()
                break
            await asyncio.sleep(5)
