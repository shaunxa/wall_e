"""Bluetooth Low Energy transport for a single SPIKE Prime hub.

This module deliberately implements discovery and connection only.  It does not
send motor commands until the higher-level SPIKE protocol implementation is
complete and tested against a real hub.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from bleak import BleakClient, BleakScanner

SPIKE_SERVICE_UUID = "0000fd02-0000-1000-8000-00805f9b34fb"
SPIKE_RX_UUID = "0000fd02-0001-1000-8000-00805f9b34fb"
SPIKE_TX_UUID = "0000fd02-0002-1000-8000-00805f9b34fb"


@dataclass(frozen=True)
class HubAdvertisement:
    """A BLE advertisement from a hub which exposes the SPIKE GATT service."""

    name: str | None
    address: str
    rssi: int | None

    def to_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


class SpikeConnection:
    """Owns one BLE connection and serializes its lifecycle."""

    def __init__(self) -> None:
        self._client: BleakClient | None = None
        self._address: str | None = None
        self._name: str | None = None
        self._received_notifications = 0
        self._last_notification_hex: str | None = None
        self._connected_at: datetime | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    async def scan(timeout_seconds: float = 5.0) -> list[HubAdvertisement]:
        """Return nearby devices advertising LEGO's SPIKE Prime service UUID."""
        devices = await BleakScanner.discover(timeout=timeout_seconds, return_adv=True)
        hubs: list[HubAdvertisement] = []
        for device, advertisement in devices.values():
            service_uuids = {uuid.lower() for uuid in advertisement.service_uuids}
            if SPIKE_SERVICE_UUID not in service_uuids:
                continue
            hubs.append(
                HubAdvertisement(
                    name=device.name or advertisement.local_name,
                    address=device.address,
                    rssi=getattr(advertisement, "rssi", None),
                )
            )
        return sorted(hubs, key=lambda hub: (hub.name or "", hub.address))

    async def connect(self, address: str) -> dict[str, Any]:
        """Connect and subscribe to hub notifications, without sending commands."""
        async with self._lock:
            if self._client and self._client.is_connected:
                if self._address == address:
                    return self.status()
                await self._disconnect_unlocked()

            client = BleakClient(address, disconnected_callback=self._on_disconnect)
            await client.connect(timeout=15.0)
            try:
                services = client.services
                characteristic_uuids = {
                    characteristic.uuid.lower()
                    for service in services
                    for characteristic in service.characteristics
                }
                missing = {SPIKE_RX_UUID, SPIKE_TX_UUID} - characteristic_uuids
                if missing:
                    raise ValueError(
                        "The connected device does not expose the SPIKE Prime GATT "
                        f"characteristics: {', '.join(sorted(missing))}."
                    )
                await client.start_notify(SPIKE_TX_UUID, self._on_notification)
            except Exception:
                await client.disconnect()
                raise

            self._client = client
            self._address = address
            self._name = getattr(client, "name", None)
            self._received_notifications = 0
            self._last_notification_hex = None
            self._connected_at = datetime.now(UTC)
            return self.status()

    async def disconnect(self) -> dict[str, Any]:
        """Disconnect from the hub. No motor control commands are sent."""
        async with self._lock:
            await self._disconnect_unlocked()
            return self.status()

    def status(self) -> dict[str, Any]:
        connected = bool(self._client and self._client.is_connected)
        return {
            "connected": connected,
            "address": self._address if connected else None,
            "name": self._name if connected else None,
            "notifications_received": self._received_notifications,
            "last_notification_hex": self._last_notification_hex,
            "connected_at": self._connected_at.isoformat() if connected and self._connected_at else None,
            "mode": "discovery-and-connection-only",
        }

    async def _disconnect_unlocked(self) -> None:
        if self._client:
            if self._client.is_connected:
                try:
                    await self._client.stop_notify(SPIKE_TX_UUID)
                except Exception:
                    pass
                await self._client.disconnect()
            self._client = None
        self._address = None
        self._name = None
        self._connected_at = None

    def _on_notification(self, _sender: Any, data: bytearray) -> None:
        self._received_notifications += 1
        self._last_notification_hex = bytes(data).hex()

    def _on_disconnect(self, _client: BleakClient) -> None:
        self._client = None
        self._address = None
        self._name = None
        self._connected_at = None
