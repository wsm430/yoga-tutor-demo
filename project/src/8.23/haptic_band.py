"""旧版兼容入口。

新代码请直接使用 :class:`esp32_controller.ESP32Controller`。
"""

from esp32_controller import ESP32Controller


class HapticBand(ESP32Controller):
    """保留旧类名，但复用统一串口控制实现。"""

    def __init__(self, port=None, auto_find=True):
        super().__init__(port=port if (port or not auto_find) else None)
        self.connect()

    def send_motors(self, motor_indices):
        return self.send_motor_command([(idx, 255) for idx in motor_indices], [])

    def stop(self):
        return self.send_stop()

    def close(self):
        self.disconnect()
