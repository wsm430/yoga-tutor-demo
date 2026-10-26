"""逐个测试触觉手环马达；默认自动识别 ESP32 串口。"""

import argparse
import time

from esp32_controller import ESP32Controller


def main():
    parser = argparse.ArgumentParser(description="逐个测试 4 个震动马达")
    parser.add_argument("--port", help="串口，例如 COM9；省略则自动识别")
    parser.add_argument("--duration", type=float, default=0.7, help="单个马达震动秒数")
    args = parser.parse_args()

    controller = ESP32Controller(port=args.port)
    if not controller.connect():
        print("未连接 ESP32。请检查数据线、驱动和串口参数。")
        return 1

    try:
        for motor in range(4):
            print(f"测试 M{motor}")
            controller.send_motor_command([(motor, 180)], [])
            time.sleep(args.duration)
            controller.send_stop()
            time.sleep(0.3)
    finally:
        controller.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
