"""ESP32 触觉手环串口控制。

没有安装 pyserial 或没有连接硬件时会静默降级，视觉功能仍可使用。
"""

from __future__ import annotations

import threading
import time
from typing import List, Optional, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # pragma: no cover - 取决于运行环境
    serial = None

from config import (
    HAPTIC_BAUD,
    HAPTIC_DEBUG,
    HAPTIC_KEEPALIVE_INTERVAL,
    HAPTIC_PORT,
    HAPTIC_RECONNECT_INTERVAL,
)
from haptic_feedback import HapticMapper


class DummyController:
    """与真实控制器接口一致的空实现，便于无硬件测试。"""

    connected = False

    def connect(self) -> bool:
        return False

    def send_motor_command(self, left_motors, right_motors) -> bool:
        return False

    def send_stop(self) -> bool:
        return False

    def disconnect(self) -> None:
        pass


class ESP32Controller(DummyController):
    USB_KEYWORDS = (
        "cp210", "ch340", "silab", "ftdi", "arduino", "esp32",
        "usb serial", "usb to uart", "usb jtag", "jtag/serial",
        "espressif", "seeed", "xiao",
    )

    def __init__(self, port: Optional[str] = HAPTIC_PORT, baud: int = HAPTIC_BAUD,
                 debug: bool = HAPTIC_DEBUG):
        self.port = port
        self.baud = baud
        self.debug = debug
        self.ser = None
        self.connected = False
        self._lock = threading.Lock()
        self._last_send: Optional[str] = None
        self._last_send_at = 0.0
        self._last_connect_attempt = 0.0

    def connect(self) -> bool:
        if self.connected:
            return True
        if serial is None:
            print("[Haptic] 未安装 pyserial，已使用无硬件模式")
            return False

        now = time.monotonic()
        if now - self._last_connect_attempt < HAPTIC_RECONNECT_INTERVAL:
            return False
        self._last_connect_attempt = now
        target = self.port or self._auto_find_port()
        if not target:
            print("[Haptic] 未发现 ESP32，已使用无硬件模式")
            return False
        try:
            self.ser = serial.Serial(target, self.baud, timeout=0.25, write_timeout=0.5)
            time.sleep(1.5)  # ESP32 打开串口后通常会复位
            self.ser.reset_input_buffer()
            self.connected = True
            self._last_send = None
            self._last_send_at = 0.0
            self._write("L:N R:N\n")
            print(f"[Haptic] 已连接 {target}")
            return True
        except Exception as exc:
            self._mark_disconnected()
            print(f"[Haptic] 连接 {target} 失败: {exc}")
            return False

    def send_motor_command(self, left_motors: List[Tuple[int, int]],
                           right_motors: List[Tuple[int, int]]) -> bool:
        if not self.connected and not self.connect():
            return False
        command = HapticMapper.to_command(left_motors, right_motors)
        now = time.monotonic()
        if (command == self._last_send and
                now - self._last_send_at < HAPTIC_KEEPALIVE_INTERVAL):
            return True
        try:
            with self._lock:
                self._write(command)
                self._last_send = command
                self._last_send_at = now
            if self.debug:
                print(f"[Haptic] TX {command.strip()}")
            return True
        except Exception as exc:
            print(f"[Haptic] 发送失败: {exc}")
            self._mark_disconnected()
            return False

    def send_stop(self) -> bool:
        return self.send_motor_command([], [])

    def disconnect(self) -> None:
        with self._lock:
            if self.ser is not None:
                try:
                    if self.ser.is_open:
                        self._write("L:N R:N\n")
                        self.ser.close()
                except Exception:
                    pass
            self._mark_disconnected()

    def _write(self, command: str) -> None:
        if self.ser is None or not self.ser.is_open:
            raise ConnectionError("串口未打开")
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def _mark_disconnected(self) -> None:
        self.connected = False
        self._last_send = None
        self._last_send_at = 0.0
        self.ser = None

    def _auto_find_port(self) -> Optional[str]:
        ports = list(serial.tools.list_ports.comports())
        for item in ports:
            text = f"{item.description or ''} {item.name or ''}".lower()
            if any(keyword in text for keyword in self.USB_KEYWORDS):
                return item.device
        # 不再盲选第一个串口，避免误操作其他串口设备。
        return None

    @staticmethod
    def list_ports():
        if serial is None:
            return []
        return [(item.device, item.description) for item in serial.tools.list_ports.comports()]
