"""ESP32 触觉腕带蓝牙（BLE）控制。

接口与 ESP32Controller 一样：connect / send_motor_command / send_stop / disconnect。
需要： pip install bleak
固件：firmware/wristband_ble（蓝牙名 YogaBand，Nordic UART 服务）。
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import List, Optional, Tuple

try:
    from bleak import BleakClient, BleakScanner
except ImportError:  # pragma: no cover
    BleakClient = None

from config import HAPTIC_KEEPALIVE_INTERVAL, HAPTIC_RECONNECT_INTERVAL
from haptic_feedback import HapticMapper

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # 电脑 -> 腕带
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # 腕带 -> 电脑
DEVICE_NAME = "YogaBand"


class BLEController:
    def __init__(self, name: str = DEVICE_NAME, debug: bool = False):
        self.name = name
        self.debug = debug
        self.connected = False
        self.client: Optional["BleakClient"] = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._last_send: Optional[str] = None
        self._last_send_at = 0.0
        self._last_connect_attempt = 0.0

    def _run(self, coro, timeout=15.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def connect(self) -> bool:
        if self.connected:
            return True
        if BleakClient is None:
            print("[Haptic] 未安装 bleak（pip install bleak），已使用无硬件模式")
            return False
        now = time.monotonic()
        if now - self._last_connect_attempt < HAPTIC_RECONNECT_INTERVAL:
            return False
        self._last_connect_attempt = now
        try:
            return self._run(self._connect())
        except Exception as exc:
            print(f"[Haptic] 蓝牙连接失败: {exc}")
            self.connected = False
            return False

    async def _connect(self) -> bool:
        print(f"[Haptic] 正在搜索蓝牙设备 {self.name} ...")
        dev = await BleakScanner.find_device_by_name(self.name, timeout=8.0)
        if dev is None:
            print(f"[Haptic] 没找到 {self.name}，确认腕带已开机、没有被其他设备连着")
            return False
        self.client = BleakClient(dev, disconnected_callback=self._on_disconnect)
        await self.client.connect()
        try:
            await self.client.start_notify(NUS_TX, self._on_notify)
        except Exception:
            pass
        self.connected = True
        self._last_send = None
        print(f"[Haptic] 已通过蓝牙连接 {self.name} ({dev.address})")
        return True

    def _on_disconnect(self, _client):
        self.connected = False
        self._last_send = None
        print("[Haptic] 蓝牙已断开")

    def _on_notify(self, _handle, data: bytearray):
        if self.debug:
            print(f"[Haptic] RX {data.decode(errors='replace').strip()}")

    def send_motor_command(self, left_motors: List[Tuple[int, int]],
                           right_motors: List[Tuple[int, int]]) -> bool:
        if not self.connected and not self.connect():
            return False
        command = HapticMapper.to_command(left_motors, right_motors)
        now = time.monotonic()
        if command == self._last_send and now - self._last_send_at < HAPTIC_KEEPALIVE_INTERVAL:
            return True
        try:
            self._run(self.client.write_gatt_char(NUS_RX, command.encode("ascii"), response=False), 3.0)
            self._last_send = command
            self._last_send_at = now
            if self.debug:
                print(f"[Haptic] TX {command.strip()}")
            return True
        except Exception as exc:
            print(f"[Haptic] 蓝牙发送失败: {exc}")
            self.connected = False
            return False

    def send_stop(self) -> bool:
        return self.send_motor_command([], [])

    def disconnect(self) -> None:
        if self.client is not None:
            try:
                if self.connected:
                    self._run(self.client.write_gatt_char(NUS_RX, b"L:N R:N\n", response=False), 3.0)
                self._run(self.client.disconnect(), 5.0)
            except Exception:
                pass
        self.connected = False
        self.client = None
