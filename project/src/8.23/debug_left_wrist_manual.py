r"""Manually send left-wrist haptic directions.

Run from the project root:
    python src\debug_left_wrist_manual.py

Commands:
    up/down/left/right, 0/1/2/3, stop, all, quit
"""

import time

from esp32_controller import ESP32Controller
from haptic_feedback import HapticMapper


DIRECTIONS = {
    "down": (HapticMapper.DOWN, "left wrist needs to move DOWN"),
    "left": (HapticMapper.LEFT, "left wrist needs to move LEFT"),
    "up": (HapticMapper.UP, "left wrist needs to move UP"),
    "right": (HapticMapper.RIGHT, "left wrist needs to move RIGHT"),
    "0": (HapticMapper.DOWN, "M0 / DOWN"),
    "1": (HapticMapper.LEFT, "M1 / LEFT"),
    "2": (HapticMapper.UP, "M2 / UP"),
    "3": (HapticMapper.RIGHT, "M3 / RIGHT"),
}


def send_direction(controller, key, duration=1.2):
    motor, label = DIRECTIONS[key]
    print(f"Send: {label} -> motor {motor}")
    controller.send_motor_command([(motor, 255)], [])
    time.sleep(duration)
    controller.send_stop()


def main():
    controller = ESP32Controller()
    if not controller.connect():
        print("Could not connect to the haptic band. Check COM9 and close Arduino Serial Monitor.")
        return 1

    print("\nLeft wrist manual haptic debug")
    print("Type: up/down/left/right, 0/1/2/3, all, stop, quit")

    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd in ("q", "quit", "exit"):
                break
            if cmd in ("s", "stop"):
                controller.send_stop()
                print("Stopped.")
                continue
            if cmd == "all":
                for key in ("down", "left", "up", "right"):
                    send_direction(controller, key)
                    time.sleep(0.4)
                continue
            if cmd in DIRECTIONS:
                send_direction(controller, cmd)
                continue

            print("Unknown command. Use: up/down/left/right, 0/1/2/3, all, stop, quit")
    finally:
        controller.send_stop()
        controller.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
