r"""Manually send the four verified left-wrist haptic directions.

Run from the project root:
    python src\debug_left_wrist_manual.py
"""

import time

from esp32_controller import ESP32Controller
from haptic_feedback import HapticMapper


DIRECTIONS = {
    "down": (HapticMapper.DOWN, "M0 / wrist bottom"),
    "left": (HapticMapper.LEFT, "M1 / wrist left"),
    "up": (HapticMapper.UP, "M2 / wrist top"),
    "right": (HapticMapper.RIGHT, "M3 / wrist right"),
    "0": (HapticMapper.DOWN, "M0 / wrist bottom"),
    "1": (HapticMapper.LEFT, "M1 / wrist left"),
    "2": (HapticMapper.UP, "M2 / wrist top"),
    "3": (HapticMapper.RIGHT, "M3 / wrist right"),
}


def send_direction(controller, key, duration=1.2, keepalive=False):
    motor, label = DIRECTIONS[key]
    if controller.ser is not None:
        controller.ser.reset_input_buffer()
    sent = controller.send_motor_command([(motor, 255)], [])
    print(f"Send: {label} ({'serial write OK' if sent else 'serial write FAILED'})")
    time.sleep(0.12)
    replies = []
    if controller.ser is not None:
        while controller.ser.in_waiting:
            reply = controller.ser.readline().decode("ascii", errors="replace").strip()
            if reply:
                replies.append(reply)
    print(f"ESP32 reply: {', '.join(replies) if replies else 'NONE'}")
    if keepalive:
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            time.sleep(0.4)
            controller.send_motor_command([(motor, 255)], [])
    else:
        time.sleep(duration)
    controller.send_stop()


def main():
    controller = ESP32Controller()
    if not controller.connect():
        print("Could not connect. Check the configured COM port and close Serial Monitor.")
        return 1

    print("\nLeft wrist manual haptic debug")
    print("Type: up/down/left/right, hold <direction>, all, stop, quit")
    try:
        while True:
            cmd = input("> ").strip().lower()
            if cmd in {"q", "quit", "exit"}:
                break
            if cmd in {"s", "stop"}:
                controller.send_stop()
                print("Stopped.")
            elif cmd == "all":
                for key in ("down", "left", "up", "right"):
                    send_direction(controller, key)
                    time.sleep(0.4)
            elif cmd.startswith("hold "):
                key = cmd.removeprefix("hold ").strip()
                if key in DIRECTIONS:
                    print("Holding for 10 seconds for voltage measurement...")
                    send_direction(controller, key, duration=10.0, keepalive=True)
                else:
                    print("Use: hold up/down/left/right")
            elif cmd in DIRECTIONS:
                send_direction(controller, cmd)
            else:
                print("Use: up/down/left/right, hold <direction>, all, stop, quit")
    finally:
        controller.send_stop()
        controller.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
