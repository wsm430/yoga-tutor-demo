"""Haptic transport: USB serial or BLE (set YOGA_HAPTIC_TRANSPORT=ble)."""

from typing import Protocol

from config import HAPTIC_TRANSPORT
from esp32_controller import DummyController, ESP32Controller


class HapticTransport(Protocol):
    connected: bool

    def connect(self) -> bool: ...
    def send_motor_command(self, left_motors, right_motors) -> bool: ...
    def send_stop(self) -> bool: ...
    def disconnect(self) -> None: ...


def create_haptic_transport(mode=None) -> HapticTransport:
    selected = (mode or HAPTIC_TRANSPORT).strip().lower()
    if selected == "serial":
        return ESP32Controller()
    if selected in {"none", "off", "disabled"}:
        return DummyController()
    if selected == "ble":
        from ble_controller import BLEController
        return BLEController()
    raise ValueError(f"Unknown haptic transport: {selected}")
