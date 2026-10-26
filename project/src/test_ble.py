"""蓝牙测试腕带：连上 YogaBand 后逐个震 M0-M3。

用法（在 src 目录下）：
    pip install bleak
    python test_ble.py        # 自动依次震 M0..M3
    python test_ble.py -i     # 交互：输入 0/1/2/3 单独震，a 全部，q 退出
"""

import argparse
import time

from ble_controller import BLEController

NAMES = {0: "M0 手腕下侧", 1: "M1 手腕左侧", 2: "M2 手腕上侧", 3: "M3 手腕右侧"}


def buzz(ctrl, m, pwm, seconds):
    print(f"-> 震动 {NAMES[m]}")
    ctrl.send_motor_command([(m, pwm)], [])
    time.sleep(seconds)
    ctrl.send_stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--interactive", action="store_true")
    ap.add_argument("--pwm", type=int, default=255)
    ap.add_argument("--seconds", type=float, default=1.5)
    args = ap.parse_args()

    ctrl = BLEController(debug=True)
    if not ctrl.connect():
        return 1
    print("已连接（腕带应该刚刚四个马达一起震了 1 秒）")
    time.sleep(1.5)
    try:
        if args.interactive:
            print("输入 0/1/2/3 震对应马达，a 依次全部，q 退出")
            while True:
                k = input("> ").strip().lower()
                if k == "q":
                    break
                targets = range(4) if k == "a" else [int(k)] if k in {"0", "1", "2", "3"} else []
                for m in targets:
                    buzz(ctrl, m, args.pwm, args.seconds)
                    time.sleep(0.5)
        else:
            for m in range(4):
                buzz(ctrl, m, args.pwm, args.seconds)
                time.sleep(0.8)
    finally:
        ctrl.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
